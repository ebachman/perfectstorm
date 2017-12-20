#!/usr/bin/python
#
# Author: Srikar Rajamani
#
import sys
import json

import errno
import requests
import yaml
#import httplib
import logging.handlers
import py2neo
import random
import argparse
import os
import re

from requests_toolbelt.multipart.encoder import MultipartEncoder
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from requests.packages.urllib3.exceptions import InsecurePlatformWarning
from requests.packages.urllib3.exceptions import SNIMissingWarning
from os.path import expanduser
from urllib.parse import urlparse

logFormatter = logging.Formatter(
    "%(asctime)s %(name)s [%(processName)-12.12s] [%(levelname)-5.5s]  %(message)s")
log = logging.getLogger('mosaix.core')

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
log.addHandler(consoleHandler)
log.setLevel(logging.INFO)

#httplib.HTTPConnection.debuglevel = 0
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.INFO)
requests_log.propagate = True
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
requests.packages.urllib3.disable_warnings(SNIMissingWarning)

def get_config_tuple(ep_env_name, creds_env_name, default_creds):
    endpoint = os.environ[ep_env_name]
    username, password = os.environ.get(creds_env_name, default_creds).split('@')
    return endpoint, username, password

def get_cloudos_info():
    return get_config_tuple('CLOUDOS_IP', 'CLOUDOS_CREDS', 'admin@admin')

def get_mkg_info():
    return get_config_tuple('MKG_DB', 'MKG_CREDS', 'neo4j@mosaix')


class cloudos_client:
    "Core APIs to communicate with Mosaix FrontEnd over REST channel"

    def __init__(self, verbose_mode=False):
        self.token = None
        self.baseurl, self.username, self.password = get_cloudos_info()
        if not self.baseurl or not self.username or not self.password:
            raise Exception('Cannot instantiate REST client without CLOUDOS info')

        self.verbose_mode = verbose_mode

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10,
                                                pool_maxsize=50, max_retries=10,
                                                pool_block=False)
        self.session.mount('http://', adapter)
        self.session.verify = False

        self.verbose(self.verbose_mode)

        self.token = self.authenticate()

    def close(self):
        self.session.close()

    def verbose(self, state):
        httplib.HTTPConnection.debuglevel = 1 if state == True else 0
        requests_log.setLevel(logging.DEBUG if state == True else logging.INFO)
        log.setLevel(logging.DEBUG if state == True else logging.INFO)

    def authenticate(self):
        d = {'username': str(self.username), 'password': str(self.password)}

        status_code, d = self.post('/api/authenticate/generate-token', d, True)
        if status_code in [httplib.FOUND, httplib.OK, httplib.CREATED,
                           httplib.ACCEPTED]:
            return d.get('token', None)

        raise Exception('authentication failed')

    def check_response(self, response):
        status = response.get('status', 'pass')
        if status.lower() in ['pass', 'success']:
            return True

        return False

    def post(self, url, data, is_login=False):
        if is_login:
            json_data = json.dumps(data)
            headers = {'Content-Type': 'application/json'}

            response = self.session.post(self.baseurl + url, data=json_data,
                                         headers=headers, allow_redirects=False)

            if response.status_code == httplib.OK:
                return (response.status_code, json.loads(response.content).get('data'))
        else:
            multipart_data = MultipartEncoder(fields=data)
            headers = {'Content-Type': multipart_data.content_type}
            if self.token:
                headers['token'] = self.token

            response = self.session.post(self.baseurl + url, data=multipart_data,
                                         headers=headers, allow_redirects=False)

        if response.status_code in [httplib.OK, httplib.CREATED,
                                    httplib.ACCEPTED]:
            d = yaml.load(response.content)
            if self.check_response(d):
                log.debug(yaml.dump(d))
                return response.status_code, d
            else:
                log.error(yaml.dump(d))
                raise Exception('post failed with error code: {}'
                                .format(response.status_code))
        else:
            raise Exception('post failed with error code: {}'
                            .format(response.status_code))

    def put(self, url, data):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['token'] = self.token

        if not data:
            data = {}
        response = self.session.put(self.baseurl + url,
                                    headers=headers, allow_redirects=False)

        if response.status_code in [httplib.OK, httplib.CREATED,
                                    httplib.ACCEPTED]:
            d = yaml.load(response.content)
            if self.check_response(d):
                log.debug(yaml.dump(d))
                return response.status_code, d
            else:
                log.error(yaml.dump(d))
                raise Exception('put failed with error code: {}'
                                .format(response.status_code))
        else:
            raise Exception('put failed with error code: {}'
                            .format(response.status_code))

    def delete(self, url):
        headers = {}
        if self.token:
            headers['token'] = self.token
        response = self.session.delete(self.baseurl + url, headers=headers)
        if response is None or response.status_code not in [httplib.OK,
                                                            httplib.ACCEPTED]:
            raise Exception('delete failed')

    def get(self, url, redirect=False):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.0; WOW64; rv:24.0) Gecko/20100101 Firefox/24.0',
            'token': self.token, 'Accept-Encoding': 'json'
        }
        try:
            cookies = {'authToken': self.token}
            response = self.session.get(self.baseurl + url, headers=headers,
                                        allow_redirects=redirect, cookies=cookies)
        except Exception as e:
            log.info('Suspect URL {}'.format(url))
            log.exception(sys.exc_info())
            raise e

        log.debug(response.text)
        if httplib.OK == response.status_code:
            d = yaml.load(response.text)
            if self.check_response(d):
                log.debug(yaml.dump(d))
                return d
            else:
                log.error(yaml.dump(d))
                raise Exception('get failed with error code: {}'
                                .format(response.status_code))


class mkg_client:
    "Query APIs to interact with neo4j (mkg) directly"

    def __init__(self):
        mkgurl, username, password = get_mkg_info()
        if not mkgurl or not username or not password:
            raise Exception('Cannot create mkg_client without mkg info')

        parsed = urlparse(mkgurl)
        py2neo.authenticate(parsed.netloc, username, password)
        if not mkgurl.endswith('/'):
            mkgurl = mkgurl + '/'
        self.mkg = py2neo.Graph(mkgurl + 'db/data/')

    def delete_all(self):
        self.mkg.delete_all()

    def get_all_clouds(self):
        return self.mkg.find('cloud')

    def get_cloud(self, cloudId):
        return self.mkg.find_one('cloud', 'name', cloudId)

    def get_cloud_tenants(self, cloudId):
        cloudNode = self.mkg.find_one('cloud', 'name', cloudId)
        rels = self.mkg.match(end_node=cloudNode, rel_type='is_in_cloud')
        return [rel.start_node for rel in rels]

    def get_cloud_images(self, cloudId):
        cloudNode = self.mkg.find_one('cloud', 'name', cloudId)
        rels = self.mkg.match(start_node=cloudNode, rel_type='has_image')
        return [rel.end_node for rel in rels]

    def get_cloud_flavors(self, cloudId):
        cloudNode = self.mkg.find_one('cloud', 'name', cloudId)
        rels = self.mkg.match(start_node=cloudNode, rel_type='cloud_has_flavor')
        return [rel.end_node for rel in rels]

    def get_flavors_for_image(self, imageNode):
        rels = self.mkg.match(start_node=imageNode, rel_type='image_has_flavor')
        return [rel.end_node for rel in rels]

    def get_networks(self, tenantNode):
        rels = self.mkg.match(start_node=tenantNode,
                              rel_type='has_access_to_network')
        return [rel.end_node for rel in rels]

    def get_subnets(self, networkNode):
        rels = self.mkg.match(start_node=networkNode, rel_type='has_subnet')
        return [rel.end_node for rel in rels]

    def get_instance_engines(self, cloudId):
        images = self.get_cloud_images(cloudId)
        for image in images:
            rels = self.mkg.match(end_node=image, rel_type='created_from_image')
            return [rel.start_node for rel in rels]

    def get_instance_engine(self, cloudId, name):
        d = {}
        engine = self.mkg.find_one('engine', 'name', name)
        if not engine:
            return

        # get the image for the engine
        rels = self.mkg.match(start_node=engine, rel_type='created_from_image')
        images = [rel.end_node for rel in rels]
        if len(images) != 1:
            raise Exception("Expected 1 image for engine. Found " + len(images))

        cloudNode = self.mkg.find_one('cloud', 'name', cloudId)
        d['cloud'] = str(cloudNode['name'])
        rels = self.mkg.match(start_node=cloudNode, rel_type='has_image')
        d['alias'] = str(engine['name'])
        d['type'] = str(engine['type'])
        d['cpu'] = str(engine['nr_cpus'])
        d['memory'] = int(float(engine['memory']))
        # d['_CreationTime'] = str(engine['_CreationTime'])

        options = json.loads(str(engine['options']))
        if options != None:
            if options.has_key('env'):
                env = [str(env) for env in options['env']]
                d['environment'] = env

            if options.has_key('ports'):
                ports = [str(ports) for ports in options['ports']]
                d['ports'] = ports

        d['image'] = str(images[0]['name'])

        # find the application node attached to the engine to find the command
        rels = self.mkg.match(end_node=engine, rel_type='runs_in_engine')
        apps = [rel.start_node for rel in rels]
        if len(apps) == 1:
            d['command'] = str(apps[0]['command'])

        # find the port attached to the engine
        rels = self.mkg.match(end_node=engine, rel_type='is_in_engine')
        ports = [rel.start_node for rel in rels]
        if len(ports) > 0 :
            subnets = self.get_subnet(ports)
            d['subnet'] = [str(s['ip_range']) for s in subnets][0]

        return {'service': d}

    def get_subnet(self, ports):
        subnets = []
        for port in ports:
            rels = self.mkg.match(start_node=port, rel_type='is_in_subnet')
            subnet = [rel.end_node for rel in rels]
            subnets.append(subnet[0])

        return subnets

    def get_host(self, cloudId):
        return self.mkg.find_one('engine', 'cloud_id', cloudId)            

    def get_workload_host(self, nodeMkgId):
        node = self.mkg.find_one('engine', 'mkgNodeId', nodeMkgId)
        if node is None:
            return None
        rels = self.mkg.match(end_node=node, rel_type='contains_engine')
        return rels.next().start_node

    def get_host_cloud(self, hostCloudId):
        engineNode = self.mkg.find_one('engine', 'cloud_id', hostCloudId)
        tenantRel = self.mkg.match(start_node=engineNode, rel_type='belongs_to_tenant')
        tenantNode = tenantRel.next().end_node
        cloudRel = self.mkg.match(start_node=tenantNode, rel_type='is_in_cloud')
        cloud = cloudRel.next().end_node
        return cloud

    def get_cloud_hosts(self, cloudName):
        # If no cloudName is specified, return  hosts in all clouds
        if cloudName is None:
            hosts = self.mkg.find('engine', 'type', 'PHYSICAL_SERVER')
            return [host for host in hosts]
        cloudNode = self.mkg.find_one('cloud', 'cloud_id', cloudName)
        if cloudNode is None:
            return None
        tenantRels = self.mkg.match(end_node=cloudNode, rel_type='is_in_cloud')
        tenantNode = tenantRels.next().start_node
        hostRels = self.mkg.match(end_node=tenantNode, rel_type='belongs_to_tenant')
        return [rel.start_node for rel in hostRels]

    def execute(self, cypher_query):
        return self.mkg.cypher.execute(cypher_query)
