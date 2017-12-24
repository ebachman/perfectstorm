# Copyright (c) 2017, Composure.ai
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

import abc
import re
import threading

from django.conf import settings

import py2neo.database


_connection_pool = threading.local()

OPERATORS = {}
TOP_LEVEL_OPERATORS = {}

_find_unsafe = re.compile(r'\W').search


class GraphException(Exception):

    pass


class DatabaseConnectionError(GraphException):

    pass


class QueryParseError(GraphException):

    pass


class ValueType:

    def __init__(self, type, name):
        self.type = type
        self.name = name

    def validate(self, value):
        expected_types = self.type if isinstance(self.type, tuple) else (self.type,)
        if type(value) not in expected_types:
            raise QueryParseError('Invalid value: {!r}, expected a {}'.format(value, self.name))
        return value


class ListOf:

    def __init__(self, subtype):
        self.subtype = subtype

    def validate(self, value):
        try:
            return [self.subtype.validate(item) for item in value]
        except TypeError:
            raise QueryParseError('Invalid value: {!r}, expected a list of {}'.format(value, self.subtype.name))


STRING = ValueType(str, 'string')
INT = ValueType(int, 'int')
BOOLEAN = ValueType(bool, 'boolean')

ELEMENTARY_TYPE = ValueType((str, int, bool), 'string, int or boolean')


def get_connection():
    try:
        return _connection_pool.connection
    except AttributeError:
        pass

    try:
        conn = py2neo.database.Graph(
            settings.NEO4J_URL,
            user=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD)
    except IOError:
        raise DatabaseConnectionError(
            "Cannot connect to {}. Check 'NEO4J_URL' in your settings file or set the environment variable 'DJANGO_NEO4J_URL'".format(settings.NEO4J_URL))

    _connection_pool.connection = conn
    return conn


def close_connection():
    try:
        conn = _connection_pool.connection
    except AttributeError:
        return

    conn.close()
    del _connection_pool.connection


def escape_value(value):
    typ = type(value)

    if typ in (int, bool):
        return repr(value)
    elif typ is str:
        value = value.replace('\\', '\\\\')
        if "'" not in value:
            return "'" + value + "'"
        else:
            return '"' + value.replace('"', r'\"') + '"'
    else:
        # Assume it's a container type.
        return '[' + ', '.join(escape_value(item) for item in value) + ']'


def escape_name(label):
    if not _find_unsafe(label):
        return label
    else:
        return '`{}`'.format(label.replace('`', '``'))


def parse_query(mapping):
    if contains_operators(mapping):
        return parse_top_level_operators(mapping)

    query = Any()

    for key, value in mapping.items():
        if key == '_id':
            query &= parse_object_id_query(value)
        elif isinstance(value, dict):
            if contains_operators(value):
                query &= parse_operators(key, value)
            else:
                query &= RelatedQuery(key, parse_query(value))
        else:
            query &= PropertyEquals(key, value)

    return query


def contains_operators(mapping):
    return any(key.startswith('$') for key in mapping)


def parse_top_level_operators(mapping):
    query = Any()

    for op, value in mapping.items():
        try:
            cls = TOP_LEVEL_OPERATORS[op]
        except KeyError:
            raise QueryParseError('Unknown top-level operator: {}'.format(op))

        if issubclass(cls, BinaryLogicalOperator):
            subqueries = [parse_query(q) for q in value]
            query &= cls(subqueries)
        else:
            raise TypeError(cls.__name__)

    return query


def parse_operators(key, mapping):
    query = Any()

    for op, value in mapping.items():
        try:
            cls = OPERATORS[op]
        except KeyError:
            raise QueryParseError('Unknown operator: {}'.format(op))

        if issubclass(cls, UnaryLogicalOperator):
            query &= cls(parse_operators(key, value))
        elif issubclass(cls, PropertyCondition):
            query &= cls(key, value)
        else:
            raise TypeError(cls.__name__)

    return query


def parse_object_id_query(mapping):
    if isinstance(mapping, str):
        return ObjectIdEquals(mapping)

    query = Any()

    for op, value in mapping.items():
        if op == '$eq':
            query &= ObjectIdEquals(value)
        elif op == '$ne':
            query &= ~ObjectIdEquals(value)
        elif op == '$in':
            query &= ObjectIdIn(value)
        elif op == '$nin':
            query &= ~ObjectIdIn(value)
        else:
            raise QueryParseError('Queries on _id support only $eq, $ne, $in and $nin, got: {}'.format(op))

    return query


def register_operator(top_level=False):
    def callback(cls):
        if not issubclass(cls, QueryOperator):
            raise TypeError('Operators must subclass QueryOperator')
        mapping = TOP_LEVEL_OPERATORS if top_level else OPERATORS
        mapping[cls.keyword] = cls
        return cls
    return callback


def run_query(query):
    result = get_connection().run(query.cypher())

    nodes = []
    for item in result:
        nodes.extend(item.values())

    return nodes


def normalize_ids(ids):
    query = ObjectIdIn(ids)
    members = run_query(query)
    return {member['cloud_id'] for member in members}


class BaseNode:

    __metaclass__ = abc.ABCMeta

    @property
    @abc.abstractmethod
    def name(self):
        raise NotImplementedError

    @abc.abstractmethod
    def cypher(self):
        raise NotImplementedError


class Node(BaseNode):

    name = None

    def __init__(self, label=None):
        self.name = 'node_{:x}'.format(id(self))
        self.label = label

    def cypher(self):
        if self.label is None:
            return '({})'.format(self.name)
        else:
            return '({}:{})'.format(self.name, escape_name(self.label))


class RelatedNode(BaseNode):

    def __init__(self, parent, child):
        self.parent = parent
        self.child = child

    @property
    def name(self):
        return self.child.name

    def cypher(self):
        return '-[]-'.join((self.parent.cypher(), self.child.cypher()))


class Query:

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def match_nodes(self, subject_node):
        raise NotImplementedError

    @abc.abstractmethod
    def where_clause(self, subject_node):
        raise NotImplementedError

    def cypher(self):
        subject_node = Node()

        match = ', '.join(match.cypher() for match in self.match_nodes(subject_node))
        where = self.where_clause(subject_node)
        ret = subject_node.name

        # XXX Using DISTINCT is suboptimal. Revisit the decision in the future.
        return 'MATCH {} WHERE {} RETURN DISTINCT {}'.format(match, where, ret)

    def __invert__(self):
        """self.__invert__()  <==>  ~self"""
        return NotOperator(self)

    def __and__(self, other):
        """self.__and__(other)  <==>  self & other"""
        return AndOperator((self, other))

    def __or__(self, other):
        """self.__or__(other)  <==>  self | other"""
        return OrOperator((self, other))

    def __str__(self):
        return self.cypher()


class SingletonQuery(Query):

    def __new__(cls):
        try:
            return cls._instance
        except AttributeError:
            cls._instance = super().__new__(cls)
            return cls._instance


class Nil(SingletonQuery):

    def match_nodes(self, subject_node):
        return [subject_node]

    def where_clause(self, subject_node):
        return 'FALSE'

    def __repr__(self):
        return 'Nil()'


class Any(SingletonQuery):

    def match_nodes(self, subject_node):
        return [subject_node]

    def where_clause(self, subject_node):
        return 'TRUE'

    def __repr__(self):
        return 'Any()'


class QueryOperator(Query):

    @property
    @abc.abstractmethod
    def keyword(self):
        raise NotImplementedError


class LogicalOperator(QueryOperator):

    @property
    @abc.abstractmethod
    def cypher_keyword(self):
        raise NotImplementedError


class UnaryLogicalOperator(LogicalOperator):

    def __init__(self, query):
        if not isinstance(query, Query):
            raise TypeError(type(query).__name__)
        self.query = query

    def match_nodes(self, subject_node):
        return self.query.match_nodes(subject_node)

    def where_clause(self, subject_node):
        return '{} ({})'.format(self.cypher_keyword, self.query.where_clause(subject_node))

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.query == other.query

    def __repr__(self):
        return '{0.__class__.__name__}({0.query!r})'.format(self)


@register_operator()
class NotOperator(UnaryLogicalOperator):

    keyword = '$not'
    cypher_keyword = 'NOT'


class BinaryLogicalOperator(LogicalOperator):

    def __new__(cls, conditions):
        conditions = cls.prepare_conditions(conditions)

        if not conditions:
            return cls.identity_element
        elif len(conditions) == 1:
            return conditions[0]

        self = super().__new__(cls)
        self.conditions = conditions

        return self

    @property
    @abc.abstractmethod
    def identity_element(cls):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def absorbing_element(cls):
        raise NotImplementedError

    @classmethod
    def prepare_conditions(cls, conditions):
        prepared_conditions = []

        for cond in conditions:
            if not isinstance(cond, Query):
                raise TypeError(type(cond).__name__)

            if cond == cls.identity_element:
                pass
            elif isinstance(cond, cls):
                prepared_conditions.extend(cond.conditions)
            else:
                prepared_conditions.append(cond)

        if cls.absorbing_element in prepared_conditions:
            return (cls.absorbing_element,)
        else:
            return tuple(prepared_conditions)

    def match_nodes(self, subject_node):
        match_nodes = []
        for cond in self.conditions:
            for node in cond.match_nodes(subject_node):
                if node not in match_nodes:
                    match_nodes.append(node)
        return match_nodes

    def where_clause(self, subject_node):
        wrap = '({})'.format
        join = ' {} '.format(self.cypher_keyword).join
        return join(wrap(cond.where_clause(subject_node)) for cond in self.conditions)

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.conditions == other.conditions

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            ', '.join(repr(cond) for cond in self.conditions))


@register_operator(top_level=True)
class AndOperator(BinaryLogicalOperator):

    keyword = '$and'
    cypher_keyword = 'AND'

    identity_element = Any()
    absorbing_element = Nil()


@register_operator(top_level=True)
class OrOperator(BinaryLogicalOperator):

    keyword = '$or'
    cypher_keyword = 'OR'

    identity_element = Nil()
    absorbing_element = Any()


class RelatedQuery(Query):

    def __init__(self, label, query):
        self.node = Node(label)
        self.query = query

    def match_nodes(self, subject_node):
        return [
            RelatedNode(subject_node, match_node)
            for match_node in self.query.match_nodes(self.node)]

    def where_clause(self, subject_node):
        return self.query.where_clause(self.node)

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.node == other.node and self.query == other.query

    def __repr__(self):
        return '{0.__class__.__name__}({0.query!r})'.format(self)


class PropertyCondition(QueryOperator):

    def __init__(self, key, value):
        self.key = key
        self.value = self.value_type.validate(value)

    @property
    @abc.abstractmethod
    def value_type(self):
        raise NotImplementedError

    def match_nodes(self, subject_node):
        return [subject_node]

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.key == other.key and self.value == other.value

    def __repr__(self):
        return '{0.__class__.__name__}({0.key!r}, {0.value!r})'.format(self)


@register_operator()
class PropertyEquals(PropertyCondition):

    keyword = '$eq'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} = {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyNotEquals(PropertyCondition):

    keyword = '$ne'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} <> {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyIn(PropertyCondition):

    keyword = '$in'

    value_type = ListOf(ELEMENTARY_TYPE)

    def where_clause(self, subject_node):
        return '{}.{} IN {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyNotIn(PropertyCondition):

    keyword = '$nin'

    value_type = ListOf(ELEMENTARY_TYPE)

    def where_clause(self, subject_node):
        return 'NOT {}.{} IN {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyRegex(PropertyCondition):

    keyword = '$regex'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} =~ {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyStartsWith(PropertyCondition):

    keyword = '$startsWith'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} STARTS WITH {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyEndsWith(PropertyCondition):

    keyword = '$endsWith'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} ENDS WITH {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyContains(PropertyCondition):

    keyword = '$contains'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} CONTAINS {}'.format(escape_name(subject_node.name), escape_name(self.key), escape_value(self.value))


@register_operator()
class PropertyGt(PropertyCondition):

    keyword = '$gt'

    value_type = INT

    def where_clause(self, subject_node):
        return '{}.{} > {}'.format(escape_name(subject_node.name), escape_name(self.key), self.value)


@register_operator()
class PropertyGte(PropertyCondition):

    keyword = '$gte'

    value_type = INT

    def where_clause(self, subject_node):
        return '{}.{} >= {}'.format(escape_name(subject_node.name), escape_name(self.key), self.value)


@register_operator()
class PropertyLt(PropertyCondition):

    keyword = '$lt'

    value_type = INT

    def where_clause(self, subject_node):
        return '{}.{} < {}'.format(escape_name(subject_node.name), escape_name(self.key), self.value)


@register_operator()
class PropertyLte(PropertyCondition):

    keyword = '$lte'

    value_type = INT

    def where_clause(self, subject_node):
        return '{}.{} <= {}'.format(escape_name(subject_node.name), escape_name(self.key), self.value)


class ObjectIdCondition(QueryOperator):

    def __init__(self, value):
        self.value = self.value_type.validate(value)

    @property
    @abc.abstractmethod
    def value_type(self):
        raise NotImplementedError

    def match_nodes(self, subject_node):
        return [subject_node]

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.value == other.value

    def __repr__(self):
        return '{0.__class__.__name__}({0.value!r})'.format(self)


class ObjectIdEquals(ObjectIdCondition):

    value_type = STRING

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*' + re.escape(self.value)
        return '{node}.cloud_id =~ {cloud_id} OR {node}.name = {value}'.format(
            node=escape_name(subject_node.name), cloud_id=escape_value(cloud_id), value=escape_value(self.value))


class ObjectIdIn(ObjectIdCondition):

    value_type = ListOf(STRING)

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*(' + '|'.join(re.escape(item) for item in self.value) + ')'
        return '{node}.cloud_id =~ {cloud_id} OR {node}.name IN {value}'.format(
            node=escape_name(subject_node.name), cloud_id=escape_value(cloud_id), value=escape_value(self.value))
