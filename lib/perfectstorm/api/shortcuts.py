import contextlib
import json
import random
import string


def _get_resource_id(resource):
    if isinstance(resource, str):
        return resource
    return resource['cloud_id']


class ShortcutsImplementation:

    def __init__(self, api):
        self.api = api

    def get_address_for(self, resource):
        port_nodes = self.api.query({
            'mkgNodeType': 'port',
            'engine': {
                '_id': _get_resource_id(resource),
            },
        })
        assert len(port_nodes) == 1, 'Found {} port nodes, expected 1'.format(len(port_nodes))

        ip_address_map = json.loads(port_nodes[0]['ip_address'])
        assert len(ip_address_map) == 1, 'Found {} IP addresses, expected 1'.format(len(ip_address_map))

        return list(ip_address_map)[0]

    def get_node_for(self, resource):
        nodes = self.api.query({
            'mkgNodeType': 'engine',
            'type': 'PHYSICAL_SERVER',
            'engine': {
                '_id': _get_resource_id(resource),
            },
        })
        assert len(nodes) == 1, 'Found {} host nodes, expected 1'.format(len(nodes))

        return nodes[0]


class Shortcuts:

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return ShortcutsImplementation(instance)
