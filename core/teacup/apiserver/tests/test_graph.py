# Copyright (c) 2017, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

import re

from django.test import TestCase

from teacup.apiserver import graph


# Supported data types.
STRING_VALUES = [
    '',
    'abc',
    'x' * 1024,
    '\U0001f642',
]

INT_VALUES = [
    0,
    123,
    -456,
    123 ** 1000,
]

BOOL_VALUES = [
    False,
    True,
]

ELEMENTARY_VALUES = (
    STRING_VALUES +
    INT_VALUES +
    BOOL_VALUES
)

CONTAINERS = [
    [],
    STRING_VALUES,
    INT_VALUES,
    BOOL_VALUES,
    STRING_VALUES + INT_VALUES + BOOL_VALUES,
]

# Unsupported data types.
FLOAT_VALUES = [
    0.0,
    1.0,
    -1.0,
    float('NaN'),
    float('Inf'),
]

NULL_VALUES = [
    None,
]

INVALID_ELEMENTARY_VALUES = (
    FLOAT_VALUES +
    NULL_VALUES +
    CONTAINERS
)

NON_STRING_VALUES = (
    INT_VALUES +
    BOOL_VALUES +
    INVALID_ELEMENTARY_VALUES
)

NON_INT_VALUES = (
    STRING_VALUES +
    BOOL_VALUES +
    INVALID_ELEMENTARY_VALUES
)

INVALID_CONTAINERS = (
    # Primitive types
    INT_VALUES +
    BOOL_VALUES +
    FLOAT_VALUES +
    NULL_VALUES +
    # Containers with unsupported primitive types
    [[value] for value in INVALID_ELEMENTARY_VALUES]
)


class CypherTest(TestCase):

    def assertCypherEquals(self, first, second):
        if isinstance(first, graph.Query):
            first = first.cypher()
        if isinstance(second, graph.Query):
            second = second.cypher()

        errmsg = 'Different Cypher queries:\n    {}\n    {}'.format(first, second)

        # The Cypher query will be in a format like "MATCH (node_xyz) WHERE ... RETURN node_xyz".
        # The suffix "xyz" is random and the same Query object might produce queries with different
        # node suffix.
        node_re = re.compile('node_[0-9a-z]+')

        # Check that the queries are the same, ignoring the node names.
        self.assertEquals(node_re.split(first), node_re.split(second), errmsg)

        # Now check whether node names correspond by checking the order which they occur in the Cypher
        # expression. These two expressions correspond:
        #
        #     MATCH (node_1), (node_2) WHERE ... RETURN node_1, node_2
        #     MATCH (node_x), (node_y) WHERE ... RETURN node_x, node_y
        #
        # The reason is that `node_1` always appears in the same position as `node_x`, and similarly for
        # `node_2` and `node_y`.
        #
        # This expressions does not correspond to the other two:
        #
        #     MATCH (node_a), (node_b) WHERE ... RETURN node_b, node_a
        #
        # The reason is that, in the `RETURN` clause, `node_a` and `node_b` were swapped and their order
        # no longer corresponds to the order of the two previous expressions.

        def nodes_indices(expr):
            nodes = node_re.findall(expr)
            # index() returns the index of the first occurrence, so if our Cypher expression contains
            # nodes ('node_x', 'node_y', 'node_z', 'node_y', 'node_x'), this function returns (1, 2, 3, 2, 1).
            return [nodes.index(node) for node in nodes]

        self.assertEquals(nodes_indices(first), nodes_indices(second), errmsg)

    def check(self, query_func, cypher_fmt, test_values, invalid_test_values):
        for value in test_values:
            actual = query_func(value)
            expected = cypher_fmt.format(value=repr(value))
            self.assertCypherEquals(actual, expected)

        for value in invalid_test_values:
            with self.assertRaises(graph.QueryParseError, msg=repr(value)):
                query_func(value)

    def test_escape_name(self):
        self.assertEquals(graph.escape_name('x'), 'x')
        self.assertEquals(graph.escape_name('x-y'), '`x-y`')
        self.assertEquals(graph.escape_name('x`y'), '`x``y`')

    def test_escape_value(self):
        self.assertEquals(graph.escape_value('hello'), "'hello'")
        self.assertEquals(graph.escape_value("hello'world"), '"hello\'world"')

    def test_property_equals(self):
        self.check(
            lambda value: graph.PropertyEquals('x', value),
            'MATCH (node_x) WHERE node_x.x = {value} RETURN DISTINCT node_x',
            ELEMENTARY_VALUES,
            INVALID_ELEMENTARY_VALUES)

    def test_property_not_equals(self):
        self.check(
            lambda value: graph.PropertyNotEquals('x', value),
            'MATCH (node_x) WHERE node_x.x <> {value} RETURN DISTINCT node_x',
            ELEMENTARY_VALUES,
            INVALID_ELEMENTARY_VALUES)

    def test_property_in(self):
        self.check(
            lambda value: graph.PropertyIn('x', value),
            'MATCH (node_x) WHERE node_x.x IN {value} RETURN DISTINCT node_x',
            CONTAINERS,
            INVALID_CONTAINERS)

    def test_property_not_in(self):
        self.check(
            lambda value: graph.PropertyNotIn('x', value),
            'MATCH (node_x) WHERE NOT node_x.x IN {value} RETURN DISTINCT node_x',
            CONTAINERS,
            INVALID_CONTAINERS)

    def test_property_regex(self):
        self.check(
            lambda value: graph.PropertyRegex('x', value),
            'MATCH (node_x) WHERE node_x.x =~ {value} RETURN DISTINCT node_x',
            STRING_VALUES,
            NON_STRING_VALUES)

    def test_property_starts_with(self):
        self.check(
            lambda value: graph.PropertyStartsWith('x', value),
            'MATCH (node_x) WHERE node_x.x STARTS WITH {value} RETURN DISTINCT node_x',
            STRING_VALUES,
            NON_STRING_VALUES)

    def test_property_ends_with(self):
        self.check(
            lambda value: graph.PropertyEndsWith('x', value),
            'MATCH (node_x) WHERE node_x.x ENDS WITH {value} RETURN DISTINCT node_x',
            STRING_VALUES,
            NON_STRING_VALUES)

    def test_property_contains(self):
        self.check(
            lambda value: graph.PropertyContains('x', value),
            'MATCH (node_x) WHERE node_x.x CONTAINS {value} RETURN DISTINCT node_x',
            ELEMENTARY_VALUES,
            INVALID_ELEMENTARY_VALUES)

    def test_property_gt(self):
        self.check(
            lambda value: graph.PropertyGt('x', value),
            'MATCH (node_x) WHERE node_x.x > {value} RETURN DISTINCT node_x',
            INT_VALUES,
            NON_INT_VALUES)

    def test_property_gte(self):
        self.check(
            lambda value: graph.PropertyGte('x', value),
            'MATCH (node_x) WHERE node_x.x >= {value} RETURN DISTINCT node_x',
            INT_VALUES,
            NON_INT_VALUES)

    def test_property_lt(self):
        self.check(
            lambda value: graph.PropertyLt('x', value),
            'MATCH (node_x) WHERE node_x.x < {value} RETURN DISTINCT node_x',
            INT_VALUES,
            NON_INT_VALUES)

    def test_property_lte(self):
        self.check(
            lambda value: graph.PropertyLte('x', value),
            'MATCH (node_x) WHERE node_x.x <= {value} RETURN DISTINCT node_x',
            INT_VALUES,
            NON_INT_VALUES)

    def test_object_id_equals(self):
        self.assertCypherEquals(
            graph.ObjectIdEquals('x'),
            r"MATCH (node_x) WHERE node_x.cloud_id =~ '([^/]*/)*x' OR node_x.name = 'x' RETURN DISTINCT node_x")

        self.assertCypherEquals(
            graph.ObjectIdEquals('x/y'),
            r"MATCH (node_x) WHERE node_x.cloud_id =~ '([^/]*/)*x\\/y' OR node_x.name = 'x/y' RETURN DISTINCT node_x")

        self.assertCypherEquals(
            graph.ObjectIdEquals('[x]'),
            r"MATCH (node_x) WHERE node_x.cloud_id =~ '([^/]*/)*\\[x\\]' OR node_x.name = '[x]' RETURN DISTINCT node_x")

        self.check(
            lambda value: graph.ObjectIdEquals(value),
            None,
            [],
            NON_STRING_VALUES)

    def test_object_id_in(self):
        self.assertCypherEquals(
            graph.ObjectIdIn(['x', 'y', 'z']),
            r"MATCH (node_x) WHERE node_x.cloud_id =~ '([^/]*/)*(x|y|z)' OR node_x.name IN ['x', 'y', 'z'] RETURN DISTINCT node_x")

        self.assertCypherEquals(
            graph.ObjectIdIn(['x', 'x/y', '[x]']),
            r"MATCH (node_x) WHERE node_x.cloud_id =~ '([^/]*/)*(x|x\\/y|\\[x\\])' OR node_x.name IN ['x', 'x/y', '[x]'] RETURN DISTINCT node_x")

        self.check(
            lambda value: graph.ObjectIdEquals(value),
            None,
            [],
            INVALID_CONTAINERS)

    def test_nil(self):
        self.assertCypherEquals(
            graph.Nil(),
            'MATCH (node_x) WHERE FALSE RETURN DISTINCT node_x')

    def test_any(self):
        self.assertCypherEquals(
            graph.Any(),
            'MATCH (node_x) WHERE TRUE RETURN DISTINCT node_x')

    def test_not(self):
        self.assertCypherEquals(
            ~graph.PropertyEquals('x', 1),
            'MATCH (node_x) WHERE NOT (node_x.x = 1) RETURN DISTINCT node_x')

    def test_and(self):
        self.assertCypherEquals(
            graph.PropertyEquals('x', 1) & graph.PropertyEquals('y', 2),
            'MATCH (node_x) WHERE (node_x.x = 1) AND (node_x.y = 2) RETURN DISTINCT node_x')

    def test_or(self):
        self.assertCypherEquals(
            graph.PropertyEquals('x', 1) | graph.PropertyEquals('y', 2),
            'MATCH (node_x) WHERE (node_x.x = 1) OR (node_x.y = 2) RETURN DISTINCT node_x')

    def test_related(self):
        self.assertCypherEquals(
            graph.RelatedQuery('label', graph.PropertyEquals('y', 2)),
            'MATCH (node_x)-[]-(node_y:label) WHERE node_y.y = 2 RETURN DISTINCT node_x')

        self.assertCypherEquals(
            graph.PropertyEquals('x', 1) & graph.RelatedQuery('label', graph.PropertyEquals('y', 2)),
            'MATCH (node_x), (node_x)-[]-(node_y:label) WHERE (node_x.x = 1) AND (node_y.y = 2) RETURN DISTINCT node_x')

        self.assertCypherEquals(
            graph.PropertyEquals('x', 1) &
                graph.RelatedQuery(
                    'y_label',
                    graph.PropertyEquals('y', 2) &
                        graph.RelatedQuery('z_label', graph.PropertyEquals('z', 3)),
                ),
            'MATCH (node_x), (node_x)-[]-(node_y:y_label), (node_x)-[]-(node_y:y_label)-[]-(node_z:z_label) WHERE (node_x.x = 1) AND ((node_y.y = 2) AND (node_z.z = 3)) RETURN DISTINCT node_x')

        self.assertCypherEquals(
            graph.PropertyEquals('x', 1) &
                graph.RelatedQuery('y_label', graph.PropertyEquals('y', 2)) &
                graph.RelatedQuery('y_label', graph.RelatedQuery('z_label', graph.PropertyEquals('z', 3))),
            'MATCH (node_a), (node_a)-[]-(node_b:y_label), (node_a)-[]-(node_c:y_label)-[]-(node_d:z_label) WHERE (node_a.x = 1) AND (node_b.y = 2) AND (node_d.z = 3) RETURN DISTINCT node_a')


class OperatorTest(TestCase):

    def setUp(self):
        self.condition1 = graph.PropertyEquals('x', 1)
        self.condition2 = graph.PropertyEquals('y', 2)
        self.condition3 = graph.PropertyEquals('z', 3)

    def test_not(self):
        cond = ~self.condition1
        self.assertIsInstance(cond, graph.NotOperator)
        self.assertIs(cond.query, self.condition1)

        with self.assertRaises(TypeError):
            graph.NotOperator('invalid')

    def test_and(self):
        cond = self.condition1 & self.condition2
        self.assertIsInstance(cond, graph.AndOperator)
        self.assertEquals(cond.conditions, (self.condition1, self.condition2))

        cond = self.condition1 & self.condition2 & self.condition3
        self.assertIsInstance(cond, graph.AndOperator)
        self.assertEquals(cond.conditions, (self.condition1, self.condition2, self.condition3))

        cond = graph.Nil() & self.condition1
        self.assertIs(cond, graph.Nil())

        cond = graph.Any() & self.condition1
        self.assertIs(cond, self.condition1)

        with self.assertRaises(TypeError):
            self.condition1 & 'invalid'

    def test_or(self):
        cond = self.condition1 | self.condition2
        self.assertIsInstance(cond, graph.OrOperator)
        self.assertEquals(cond.conditions, (self.condition1, self.condition2))

        cond = self.condition1 | self.condition2 | self.condition3
        self.assertIsInstance(cond, graph.OrOperator)
        self.assertEquals(cond.conditions, (self.condition1, self.condition2, self.condition3))

        cond = graph.Nil() | self.condition1
        self.assertIs(cond, self.condition1)

        cond = graph.Any() | self.condition1
        self.assertIs(cond, graph.Any())

        with self.assertRaises(TypeError):
            self.condition1 | 'invalid'


class ParserTest(TestCase):

    def test_eq(self):
        self.assertEquals(
            graph.parse_query({'x': 1}),
            graph.PropertyEquals('x', 1))

        self.assertEquals(
            graph.parse_query({'x': {'$eq': 1}}),
            graph.PropertyEquals('x', 1))

    def test_ne(self):
        self.assertEquals(
            graph.parse_query({'x': {'$ne': 1}}),
            graph.PropertyNotEquals('x', 1))

    def test_in(self):
        self.assertEquals(
            graph.parse_query({'x': {'$in': [1, 2, 3]}}),
            graph.PropertyIn('x', [1, 2, 3]))

    def test_nin(self):
        self.assertEquals(
            graph.parse_query({'x': {'$nin': [1, 2, 3]}}),
            graph.PropertyNotIn('x', [1, 2, 3]))

    def test_regex(self):
        self.assertEquals(
            graph.parse_query({'x': {'$regex': 'abc'}}),
            graph.PropertyRegex('x', 'abc'))

    def test_starts_with(self):
        self.assertEquals(
            graph.parse_query({'x': {'$startsWith': 'abc'}}),
            graph.PropertyStartsWith('x', 'abc'))

    def test_ends_with(self):
        self.assertEquals(
            graph.parse_query({'x': {'$endsWith': 'abc'}}),
            graph.PropertyEndsWith('x', 'abc'))

    def test_contains(self):
        self.assertEquals(
            graph.parse_query({'x': {'$contains': 1}}),
            graph.PropertyContains('x', 1))

    def test_gt(self):
        self.assertEquals(
            graph.parse_query({'x': {'$gt': 1}}),
            graph.PropertyGt('x', 1))

    def test_gte(self):
        self.assertEquals(
            graph.parse_query({'x': {'$gte': 1}}),
            graph.PropertyGte('x', 1))

    def test_lt(self):
        self.assertEquals(
            graph.parse_query({'x': {'$lt': 1}}),
            graph.PropertyLt('x', 1))

    def test_lte(self):
        self.assertEquals(
            graph.parse_query({'x': {'$lte': 1}}),
            graph.PropertyLte('x', 1))

    def test_id_eq(self):
        self.assertEquals(
            graph.parse_query({'_id': 'x'}),
            graph.ObjectIdEquals('x'))

        self.assertEquals(
            graph.parse_query({'_id': {'$eq': 'x'}}),
            graph.ObjectIdEquals('x'))

    def test_id_ne(self):
        self.assertEquals(
            graph.parse_query({'_id': {'$ne': 'x'}}),
            graph.NotOperator(graph.ObjectIdEquals('x')))

    def test_id_in(self):
        self.assertEquals(
            graph.parse_query({'_id': {'$in': ['x', 'y', 'z']}}),
            graph.ObjectIdIn(['x', 'y', 'z']))

    def test_id_nin(self):
        self.assertEquals(
            graph.parse_query({'_id': {'$nin': ['x', 'y', 'z']}}),
            graph.NotOperator(graph.ObjectIdIn(['x', 'y', 'z'])))

    def test_not(self):
        self.assertEquals(
            graph.parse_query({'x': {'$not': {'$eq': 1}}}),
            graph.NotOperator(graph.PropertyEquals('x', 1)))

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'$not': {'x': 1}})

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'x': {'$eq': {'$not': 1}}}),

    def test_and(self):
        self.assertIn(
            graph.parse_query({'x': 1, 'y': 2}),
            [
                # dict order is not guaranteed
                graph.AndOperator((graph.PropertyEquals('x', 1), graph.PropertyEquals('y', 2))),
                graph.AndOperator((graph.PropertyEquals('y', 2), graph.PropertyEquals('x', 1))),
            ])

        self.assertEquals(
            graph.parse_query({'$and': [{'x': 1}, {'y': 2}]}),
            graph.AndOperator((graph.PropertyEquals('x', 1), graph.PropertyEquals('y', 2))))

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'x': {'$and': [1, 2]}})

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'x': {'$and': [{'$eq': 1}, {'$eq': 2}]}})

    def test_or(self):
        self.assertEquals(
            graph.parse_query({'$or': [{'x': 1}, {'y': 2}]}),
            graph.OrOperator((graph.PropertyEquals('x', 1), graph.PropertyEquals('y', 2))))

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'x': {'$or': [1, 2]}})

        with self.assertRaises(graph.QueryParseError):
            graph.parse_query({'x': {'$or': [{'$eq': 1}, {'$eq': 2}]}})

    def test_related(self):
        query = graph.parse_query({'x': {'y': 2}})
        self.assertIsInstance(query, graph.RelatedQuery)
        self.assertEquals(query.node.label, 'x')
        self.assertEquals(query.query, graph.PropertyEquals('y', 2))

        query = graph.parse_query({'x': {'y': {'z': 3}}})
        self.assertIsInstance(query, graph.RelatedQuery)
        self.assertEquals(query.node.label, 'x')
        self.assertIsInstance(query.query, graph.RelatedQuery)
        self.assertEquals(query.query.node.label, 'y')
        self.assertEquals(query.query.query, graph.PropertyEquals('z', 3))

        query = graph.parse_query({'$and': [{'x': {'y': 2}}, {'x': {'y': 3}}]})
        self.assertIsInstance(query, graph.AndOperator)
        a, b = query.conditions
        self.assertIsInstance(a, graph.RelatedQuery)
        self.assertIsInstance(b, graph.RelatedQuery)
        self.assertNotEquals(a, b)
        self.assertNotEquals(a.node, b.node)
        self.assertNotEquals(a.query, b.query)


class RunTest(TestCase):

    def test_name_escaping(self):
        graph.run_query(graph.PropertyEquals('x', 1))
        graph.run_query(graph.PropertyEquals('x y', 1))
        graph.run_query(graph.PropertyEquals('x`y', 1))
        graph.run_query(graph.PropertyEquals('\0', 1))
        graph.run_query(graph.PropertyEquals('\u03bb', 1))

    def test_value_escaping(self):
        graph.run_query(graph.PropertyEquals('x', 'hello'))
        graph.run_query(graph.PropertyEquals('x', 'hello world'))
        graph.run_query(graph.PropertyEquals('x', 'hello\\world'))
        graph.run_query(graph.PropertyEquals('x', '"hello world"'))
        graph.run_query(graph.PropertyEquals('x', "'hello world'"))
        graph.run_query(graph.PropertyEquals('x', '\0'))
        graph.run_query(graph.PropertyEquals('x', '\u03bb'))

    def test_nil(self):
        nodes = graph.run_query(graph.Nil())
        self.assertEquals(nodes, [])

    def test_any(self):
        graph.run_query(graph.Any())

    def test_eq(self):
        graph.run_query(graph.PropertyEquals('mkgNodeType', 'network'))

    def test_ne(self):
        graph.run_query(graph.PropertyNotEquals('mkgNodeType', 'network'))

    def test_in(self):
        graph.run_query(graph.PropertyIn('mkgNodeType', ['network', 'engine']))

    def test_nin(self):
        graph.run_query(graph.PropertyNotIn('mkgNodeType', ['network', 'engine']))

    def test_regex(self):
        graph.run_query(graph.PropertyRegex('mkgNodeType', 'network|engine'))

    def test_starts_with(self):
        graph.run_query(graph.PropertyStartsWith('mkgNodeType', 'net'))

    def test_ends_with(self):
        graph.run_query(graph.PropertyStartsWith('mkgNodeType', 'work'))

    def test_contains(self):
        graph.run_query(graph.PropertyContains('mkgNodeType', 'net'))

    def test_gt(self):
        graph.run_query(graph.PropertyGt('mkgNodeId', 500))

    def test_gte(self):
        graph.run_query(graph.PropertyGte('mkgNodeId', 500))

    def test_lt(self):
        graph.run_query(graph.PropertyLt('mkgNodeId', 500))

    def test_lte(self):
        graph.run_query(graph.PropertyLte('mkgNodeId', 500))

    def test_id_eq(self):
        graph.run_query(graph.ObjectIdEquals('network'))

    def test_id_in(self):
        graph.run_query(graph.ObjectIdIn(['x', 'y']))
