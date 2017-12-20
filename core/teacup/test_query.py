import apiserver.graph as graph

queries  = [
	{'type': 'CONTAINER', 'image': {'name': {'$regex': '459.*'}}},
	{'mkgNodeType': 'image', 'name': {'$regex': '459.*'}},
	{'mkgNodeType': 'image', 'name': {'$ne': '4590'}},
	{'mkgNodeType': 'image', 'name': {'$in': ['4590']}},
	{'mkgNodeType': 'image', 'name': {'$startsWith': '45'}},
	{'mkgNodeType': 'image', 'name': {'$endsWith': '0'}},
	{'mkgNodeType': 'image', 'name': {'$contains': '90'}},
	{'x': {'$gt': 90, '$lt': 100}},
    {
        '$or': [
            {'x': 5},
            {'x': 7},
        ],
        '$and': [
            {'y': {'$not': {'$eq': 8}}},
            {'z': 9},
        ],
    },
]

for query in queries:
	cypher = graph.parse_query(query)
	print(cypher)
	#print(graph.run_query(cypher))
