from __future__ import print_function
import nltk
from nltk.tag import RegexpTagger as RegexpTagger
from nltk.tokenize import SExprTokenizer as SExprTokenizer
from nltk.parse import RecursiveDescentParser as RecursiveDescentParser
from nltk.parse import ChartParser as ChartParser
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.corpus import wordnet
from nltk import conlltags2tree, tree2conlltags
from nltk.stem.snowball import SnowballStemmer
from itertools import chain

COMPOSURE_GRAMMAR = r"""
  NP : {<DT|PP\$>?<JJ.*>*<NN.*>+}       # Chunk determiner/possessive, adjectives and noun
  PP: {<IN><NP>}                        # Chunk prepositions followed by NP
  VP: {<VB.*><NP|PP|CD|CLAUSE>+$}       # Chunk verbs and their arguments
  CLAUSE: {<NP><VP>}                    # Chunk NP, VP
"""

COMPOSURE_OBJ_NAMES = [
    'cloud', 'image', 'flavor', 'tenant', 'engine', 'network', 'subnet', 'port', 'application', 'manager',
]
COMPOSURE_OBJ_TYPES = dict(zip(COMPOSURE_OBJ_NAMES, range(len(COMPOSURE_OBJ_NAMES))))
COMPOSURE_SYNSETS = {COMPOSURE_OBJ_NAMES[i] : [COMPOSURE_OBJ_NAMES[i]] for i in range(len(COMPOSURE_OBJ_NAMES))}

COMPOSURE_SYNSETS['engine'].extend(['container', 'vm', 'physical_server', 'router'])

DATA_MODEL = {}

for obj_name in COMPOSURE_OBJ_NAMES:
    DATA_MODEL[COMPOSURE_OBJ_TYPES[obj_name]] = [None for i in range(len(COMPOSURE_OBJ_NAMES))]

def add_edge(n1,n2, edge_name):
    global DATA_MODEL
    DATA_MODEL[COMPOSURE_OBJ_TYPES[n1]][COMPOSURE_OBJ_TYPES[n2]] = edge_name
    DATA_MODEL[COMPOSURE_OBJ_TYPES[n2]][COMPOSURE_OBJ_TYPES[n1]] = edge_name

def populate_datamodel():
    add_edge('cloud', 'image', 'has_image')
    add_edge('cloud', 'tenant', 'is_in_cloud')

    add_edge('image', 'flavor', 'image_has_flavor')
    add_edge('image', 'engine', 'created_from_image')

    add_edge('flavor', 'engine', 'launched_from_flavor')

    add_edge('engine', 'engine', 'contains_engine')
    add_edge('engine', 'manager', 'manages_engine')
    add_edge('engine', 'tenant', 'belongs_to_tenant')
    add_edge('engine', 'application', 'runs_in_engine')
    add_edge('engine', 'port', 'is_in_engine')
    add_edge('engine', 'network', 'contains_network')

    add_edge('port', 'subnet', 'is_in_subnet')

    add_edge('subnet', 'network', 'has_subnet')
    add_edge('network', 'tenant', 'has_access_to_network')

populate_datamodel()

def get_edge(n1, n2):
    global DATA_MODEL
    if n1 in COMPOSURE_OBJ_NAMES and n2 in COMPOSURE_OBJ_NAMES:
        return DATA_MODEL[COMPOSURE_OBJ_TYPES[n1]][COMPOSURE_OBJ_TYPES[n2]]

#import json
#print(json.dumps(COMPOSURE_SYNSETS, indent=4))

def find_closest_match(word, need_key=True):
    if not word:
        return None

    for k, vlist in COMPOSURE_SYNSETS.items():
        if k in word:
            return k
        for v in vlist:
            if v in word:
                if need_key:
                    return k
                return v

    return '.' + word


def extract_type(result):
    if type(result) is list:
        if not len(result):
            return None, None
        if len(result) == 1:
            return find_closest_match(result[0]), result[0]
        else:
            res_type = find_closest_match(result[0])
            return '.'.join([res_type] + result[1:-1]), result[-1]
    return None, None


def transform_to_cypher(subj, positional_context, obj):
    cypher = 'MATCH (n:{})'.format(subj[0])
    subj_type = find_closest_match(subj[1], need_key=False)

    subj_res_type = find_closest_match(subj[1])
    obj_res_type = find_closest_match(obj[0])

    match_clauses = []
    where_clauses = []
    from_node = subj_res_type
    clauses = [obj, positional_context]
    i = 0
    for i in range(len(clauses)):
        clause = clauses[i]
        t, v = clause
        if not t:
            continue

        res = find_closest_match(t)
        if '.' in t:
            res,attr = t.split('.')
            res = find_closest_match(res)
            var_name = 'var{}.{}'.format(i, attr)
            if not res:
                var_name = 'n'
            where_clauses.append('({}=~{})'.format(var_name, v))

        edge = get_edge(from_node, find_closest_match(res))
        if edge:
            match_clauses.append('[:{}]-(var{}:{})'.format(edge, i, res))
        from_node = res


    type_str = 'mkgNodeType'
    if subj_type not in COMPOSURE_SYNSETS.keys():
        type_str = 'type'
        subj_type = subj_type.upper()
    else:
        subj_type = subj_type.lower()
    where_clauses.append('n.{} = "{}"'.format(type_str, subj_type))

    if len(match_clauses):
        cypher += '-' + '-'.join(match_clauses)

    if len(where_clauses) > 0:
        cypher += ' WHERE ' + ' AND '.join(where_clauses)

    cypher += ' RETURN n'

    return cypher


def process_query(query):
    result =  nltk.RegexpParser(COMPOSURE_GRAMMAR).parse(nltk.pos_tag(query.split()))
    #print(result)
    subj = extract_type(extract_subject(result))
    pcontext = extract_type(extract_positional_context(result))
    obj = extract_type(extract_object(result))

    cypher = transform_to_cypher(subj, pcontext, obj)
    return cypher

    #result.draw()

def dprint(tree_node):
    if not tree_node:
        print('None')
        return

    leaves = tree_node.leaves()
    if leaves:
        print(leaves)
        return

    print(tree_node)


def traverse(t):
    try:
        t.label()
    except AttributeError:
        print(t, end=" ")
    else:
        print('{', t.label(), end=' ')
        for child in t:
            traverse(child)
        print('}', end=' ')


def collect(t, key, results):
    try:
        label = t.label()
    except AttributeError:
        word,pos = t
        if pos.startswith(key):
            results.append(word)
    else:
        for child in t:
            collect(child, key, results)

def extract_phrase(result, ptype):
    for i in range(len(result)):
        try:
            label = result[i].label()
        except AttributeError:
            continue
        else:
            if label == ptype:
                return result[i]


def extract_np(result):
    return extract_phrase(result, 'NP')

def extract_pp(result):
    return extract_phrase(result, 'PP')

def extract_vp(result):
    return extract_phrase(result, 'VP')

def extract_subject(result):
    np = extract_np(result)
    if not np:
        return None
    words = []
    collect(np, 'NN', words)
    return words

def extract_positional_context(result):
    pp = extract_pp(result)
    if not pp:
        return None

    words = []
    collect(pp, 'NN', words)
    return words

def extract_object(result):
    vp = extract_vp(result)
    if not vp:
        return None
    words = []
    collect(vp, 'NN', words)
    return words