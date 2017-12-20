import utils
import os
import py2neo
import json

from storm_query import process_query

os.environ['MKG_DB'] = 'http://192.168.122.72:7474'

mkg_client = utils.mkg_client()

print([c['name'] for c in mkg_client.get_all_clouds()])

'''
query = 'MATCH (i:image)-[:has_image]-(cloud) WHERE i.name =~ "459.*" RETURN i, cloud'
result = mkg_client.mkg.cypher.execute(query)
for r in result:
    print('{}'.format(list(r)))

query = 'MATCH (e:engine)-[:created_from_image]-(i:image)-[:has_image]-(c:cloud) WHERE i.name =~ "459.*" AND c.name = "cloud8" RETURN i, e, c'
result = mkg_client.mkg.cypher.execute(query)
for r in result:
    i, e, c = r
    print('{}:{}'.format(i['name'], i['mkgNodeType']))
    print('{}:{}'.format(e['name'], e['mkgNodeType']))
    print('{}:{}'.format(c['name'], c['mkgNodeType']))

query = 'MATCH (e:engine)-[:created_from_image]-(i:image)-[:has_image]-(c:cloud) WHERE i.name =~ "459.*" AND c.name = "cloud8" RETURN e'
result = mkg_client.mkg.cypher.execute(query)
for r in result:
    print('{}:{}'.format(r.e.properties['name'], r.e.properties['mkgNodeType']))

'''
sentences = [
    'containers in cloud name "cloud8" and created from image with name "4590"',
    'all images in cloud name "cloud8" with name "4590"',
    'all clouds',
#    'all engines having name "97cd-80"',
#    'engines in cloud8 with name abc'
]

for sentence in sentences[:]:
    print(sentence)
    cypher = process_query(query=sentence)
    print('Cypher: {}'.format(cypher))
    result = mkg_client.execute(cypher)
    for r in result:
        print('{}:{}'.format(r.n.properties['name'], r.n.properties['mkgNodeType']))