import abc
import re
import threading

from django.conf import settings

import py2neo.database


_connection_pool = threading.local()

OPERATORS = {}
TOP_LEVEL_OPERATORS = {}


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
        if not isinstance(value, self.type):
            raise QueryParseError('Invalid value: {!r}, expected a {}'.format(value, self.name))
        return value


class ListOf:

    def __init__(self, subtype):
        self.subtype = subtype

    def validate(self, value):
        try:
            return [self.subtype.validate(item) for item in value]
        except TypeError:
            raise QueryParseError('Invalid value: {!r}, expected a list of {}'.format(value, self.name))


STRING = ValueType(str, 'string')
NUMBER = ValueType((int, float), 'number')
BOOLEAN = ValueType(bool, 'boolean')
NULL = ValueType(type(None), 'null')

ELEMENTARY_TYPE = ValueType((str, int, float, bool, type(None)), 'string, number, boolean or null')


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
                query &= RelatedQuery(parse_query(value))
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
        elif op == '$in':
            query &= ObjectIdIn(value)
        elif op == '$nin':
            query &= ObjectIdNotIn(value)
        elif op == '$ne':
            query &= ObjectIdNotEquals(value)
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
            return '({}:{})'.format(self.name, self.label)


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

    def __not__(self):
        return NotOperator(self)

    def __and__(self, other):
        return AndOperator((self, other))

    def __or__(self, other):
        return OrOperator((self, other))

    def __str__(self):
        return self.cypher()

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self.cypher())


class Nil(Query):

    def match_nodes(self, subject_node):
        return [subject_node]

    def where_clause(self, subject_node):
        return 'FALSE'


class Any(Query):

    def match_nodes(self, subject_node):
        return [subject_node]

    def where_clause(self, subject_node):
        return 'TRUE'


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
        self.query = query

    def match_nodes(self, subject_node):
        return self.query.match_nodes(subject_node)

    def where_clause(self, subject_node):
        return '{} ({})'.format(self.cypher_keyword, self.query.where_clause(subject_node))


@register_operator()
class NotOperator(UnaryLogicalOperator):

    keyword = '$not'
    cypher_keyword = 'NOT'


class BinaryLogicalOperator(LogicalOperator):

    def __init__(self, conditions):
        self.conditions = list(self.prepare_conditions(conditions))

    @abc.abstractmethod
    def prepare_conditions(self, conditions):
        return conditions

    def match_nodes(self, subject_node):
        match_nodes = set()
        for cond in self.conditions:
            match_nodes.update(cond.match_nodes(subject_node))
        return match_nodes

    def where_clause(self, subject_node):
        wrap = '({})'.format
        join = ' {} '.format(self.cypher_keyword).join
        return join(wrap(cond.where_clause(subject_node)) for cond in self.conditions)


@register_operator(top_level=True)
class AndOperator(BinaryLogicalOperator):

    keyword = '$and'
    cypher_keyword = 'AND'

    def prepare_conditions(self, conditions):
        for cond in conditions:
            if isinstance(cond, Any):
                pass
            elif isinstance(cond, AndOperator):
                yield from cond.conditions
            else:
                yield cond


@register_operator(top_level=True)
class OrOperator(BinaryLogicalOperator):

    keyword = '$or'
    cypher_keyword = 'OR'

    def prepare_conditions(self, conditions):
        for cond in conditions:
            if isinstance(cond, Nil):
                pass
            elif isinstance(cond, OrOperator):
                yield from cond.conditions
            else:
                yield cond


class RelatedQuery(Query):

    def __init__(self, query):
        self.node = Node()
        self.query = query

    def match_nodes(self, subject_node):
        return [
            RelatedNode(subject_node, match_node)
            for match_node in self.query.match_nodes(self.node)]

    def where_clause(self, subject_node):
        return self.query.where_clause(self.node)


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


@register_operator()
class PropertyEquals(PropertyCondition):

    keyword = '$eq'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} = {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyNotEquals(PropertyCondition):

    keyword = '$ne'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} <> {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyIn(PropertyCondition):

    keyword = '$in'

    value_type = ListOf(ELEMENTARY_TYPE)

    def where_clause(self, subject_node):
        return '{}.{} IN {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyNotIn(PropertyCondition):

    keyword = '$nin'

    value_type = ListOf(ELEMENTARY_TYPE)

    def where_clause(self, subject_node):
        return 'NOT {}.{} IN {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyRegex(PropertyCondition):

    keyword = '$regex'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} =~ {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyStartsWith(PropertyCondition):

    keyword = '$startsWith'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} STARTS WITH {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyEndsWith(PropertyCondition):

    keyword = '$endsWith'

    value_type = STRING

    def where_clause(self, subject_node):
        return '{}.{} ENDS WITH {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyContains(PropertyCondition):

    keyword = '$contains'

    value_type = ELEMENTARY_TYPE

    def where_clause(self, subject_node):
        return '{}.{} CONTAINS {!r}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyGt(PropertyCondition):

    keyword = '$gt'

    value_type = NUMBER

    def where_clause(self, subject_node):
        return '{}.{} > {}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyGte(PropertyCondition):

    keyword = '$gte'

    value_type = NUMBER

    def where_clause(self, subject_node):
        return '{}.{} >= {}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyLt(PropertyCondition):

    keyword = '$lt'

    value_type = NUMBER

    def where_clause(self, subject_node):
        return '{}.{} < {}'.format(subject_node.name, self.key, self.value)


@register_operator()
class PropertyLte(PropertyCondition):

    keyword = '$lte'

    value_type = NUMBER

    def where_clause(self, subject_node):
        return '{}.{} <= {}'.format(subject_node.name, self.key, self.value)


class ObjectIdCondition(QueryOperator):

    def __init__(self, value):
        self.value = self.value_type.validate(value)

    @property
    @abc.abstractmethod
    def value_type(self):
        raise NotImplementedError

    def match_nodes(self, subject_node):
        return [subject_node]


class ObjectIdEquals(ObjectIdCondition):

    value_type = STRING

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*' + re.escape(self.value)
        return '{node}.cloud_id =~ {cloud_id!r} OR {node}.name = {value!r}'.format(
            node=subject_node.name, cloud_id=cloud_id, value=self.value)


class ObjectIdNotEquals(ObjectIdCondition):

    value_type = STRING

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*' + re.escape(self.value)
        return '{node}.cloud_id <> {cloud_id!r} AND {node}.name <> {value!r}'.format(
            node=subject_node.name, cloud_id=cloud_id, value=self.value)


class ObjectIdIn(ObjectIdCondition):

    value_type = ListOf(STRING)

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*(' + '|'.join(re.escape(item) for item in self.value) + ')'
        return '{node}.cloud_id =~ {cloud_id!r} OR {node}.name IN {value!r}'.format(
            node=subject_node.name, cloud_id=cloud_id, value=self.value)


class ObjectIdNotIn(ObjectIdCondition):

    value_type = ListOf(STRING)

    def where_clause(self, subject_node):
        cloud_id = '([^/]*/)*(' + '|'.join(re.escape(item) for item in self.value) + ')'
        return 'NOT {node}.cloud_id =~ {cloud_id!r} AND NOT {node}.name IN {value!r}'.format(
            node=subject_node.name, cloud_id=cloud_id, value=self.value)
