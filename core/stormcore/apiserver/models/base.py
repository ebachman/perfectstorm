import copy
import functools
import re
import uuid

from mongoengine import Document, QuerySet, IntField, StringField, CASCADE
from mongoengine.base import get_document
from mongoengine.base.metaclasses import MetaDict
from mongoengine.fields import BaseField
from mongoengine.queryset import Q


MetaDict._merge_options += ('lookup_fields',)


def b62uuid_encode(uuid):
    """Return the base62 encoding of the given UUID.

    Base62 strings consist of digits (0-9) and letters (A-Z, a-z).
    """
    n = uuid.int
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

    # UUIDs are 128-bit numbers. When using base 62, the resulting string will
    # be 22-characters long.
    result = ['0'] * 22

    for i in range(21, -1, -1):
        n, m = divmod(n, 62)
        result[i] = alphabet[m]

    return ''.join(result)


def b62uuid_new(prefix=None, method=uuid.uuid1):
    """Generate a new base62-encoded UUID.

    By default, this generates a new UUID using the UUID1 method. The resulting
    string can have an optional prefix.
    """
    s = b62uuid_encode(method())
    if prefix is not None:
        s = prefix + s
    return s


def prepare_user_query(model, query):
    if 'id' in query:
        query['_id'] = query.pop('id')

    remove_keys = []

    for key, value in query.items():
        if key.startswith('$'):
            if isinstance(value, list):
                for item in value:
                    prepare_user_query(model, item)
            else:
                prepare_user_query(model, value)
        elif '\0' in key or '$' in key:
            remove_keys.append(key)
        else:
            field = model._fields.get(key)
            if isinstance(field, StormReferenceField):
                doctype = field.document_type
                try:
                    document = doctype.objects.only('id').lookup(value)
                except Exception:
                    continue
                query[key] = document.id

    for key in remove_keys:
        del query[key]


def user_query_filter(query, queryset):
    if query:
        query = copy.deepcopy(query)
        prepare_user_query(queryset._document, query)
        queryset = queryset.filter(__raw__=query)
    return queryset


def _escape_char(matchobj, chr=chr, ord=ord):
    # 0x2f is the character after '.'. All characters after '.' are allowed.
    return '\x1b' + chr(0x2f + ord(matchobj.group(0)))


def _unescape_char(matchobj, chr=chr, ord=ord):
    return chr(ord(matchobj.group(1)) - 0x2f)


_escape_key = functools.partial(
    re.compile(r'[\0\x1b$.]').sub, _escape_char)

_unescape_key = functools.partial(
    re.compile(r'\x1b(.)').sub, _unescape_char)


def _replace_keys(obj, replace_key_func):
    if isinstance(obj, dict):
        new_dict = {}

        for key, value in obj.items():
            key = replace_key_func(key)
            value = _replace_keys(value, replace_key_func)
            new_dict[key] = value

        return new_dict
    elif isinstance(obj, list):
        return [_replace_keys(item, replace_key_func) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_replace_keys(item, replace_key_func) for item in obj)
    else:
        # Assume this is a primitive type, or an unsupported type (in which
        # case BSON will take care of raising an exception).
        return obj


def escape_keys(obj):
    r"""
    Replace '\0', '$' and '.' in dictionary keys with other character sequences
    that are accepted by BSON.
    """
    return _replace_keys(obj, _escape_key)


def unescape_keys(obj):
    """
    Restore dictionary keys that were escaped by escape_keys().
    """
    return _replace_keys(obj, _unescape_key)


class EscapedDictField(BaseField):
    r"""
    A DictField-like field that allows any kind of keys in dictionaries.

    Specifically, it allows any key starting with '_', it does not treat
    any keys in a special way (such as '_cls') and transparently escapes
    forbidden BSON characters ('\0', '$' and '.') before saving.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', dict)
        super().__init__(*args, **kwargs)

    def validate(self, value):
        if not isinstance(value, dict):
            self.error('Expected a dictionary, got {!r}'.format(
                type(value).__name__))
        super().validate(value)

    def to_mongo(self, value, *args, **kwargs):
        return escape_keys(value)

    def to_python(self, value):
        return unescape_keys(value)


class StormIdField(StringField):
    """ID composed of a base62-encoded UUID and a prefx.

    Example: 'res-5ntqaD7PPwP2AgXIqQsOwm'. Here 'res-' is the prefix and
    '5ntqaD7PPwP2AgXIqQsOwm' is the base62-encoded UUID.
    """

    _auto_gen = True

    def generate(self, owner=None):
        if owner is None:
            owner = self.owner_document
        prefix = owner._meta['id_prefix']
        return b62uuid_new(prefix)


class StormReferenceField(BaseField):
    """
    This is a ReferenceField-like field capable of referencing objects
    with multiple lookup fields.
    """

    # TODO Consider creating a lazy version of this class, in a way
    # TODO similar to LazyReferenceField.

    def __init__(self, document_type, reverse_delete_rule=CASCADE, **kwargs):
        self._document_type = document_type
        self.reverse_delete_rule = reverse_delete_rule
        super().__init__(**kwargs)

    @property
    def document_type(self):
        if isinstance(self._document_type, str):
            self._document_type = get_document(self._document_type)
        return self._document_type

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = instance._data.get(self.name)

        if value is not None and not isinstance(value, Document):
            try:
                document = self.document_type.objects.lookup(value)
            except Exception:
                document = None
            instance._data[self.name] = document

        return super().__get__(instance, owner)

    def to_mongo(self, value):
        if isinstance(value, Document):
            value = value.id
        return value

    def prepare_query_value(self, op, value):
        value = super().prepare_query_value(op, value)
        return self.to_mongo(value)


class AutoIncrementField(IntField):

    _auto_gen = True

    COUNTER_INCREMENT = """\
        function() {
            db.counters.findAndModify({
                query: { _id: options.counter_name },
                update: {
                    $setOnInsert: { count: 1 }
                },
                upsert: true
            });

            return db.counters.findAndModify({
                query: { _id: options.counter_name },
                update: {
                    $inc: { count: 1 },
                },
                new: true
            });
        }
    """

    def generate(self):
        counter_name = self.owner_document.__name__.lower()
        result = self.owner_document.objects.exec_js(
            self.COUNTER_INCREMENT, counter_name=counter_name)
        return int(result['count'])


class StormQuerySet(QuerySet):

    def lookup(self, value):
        lookup_fields = self._document._meta['lookup_fields']

        if value is None or not lookup_fields:
            raise self.DoesNotExist(
                '{} matching query does not exist.'.format(
                    self.__class__._meta.object_name))

        query = Q()
        for key in lookup_fields:
            query |= Q(**{key: value})

        return self.get(query)


class StormDocument(Document):

    id = StormIdField(primary_key=True, required=True, null=False)

    meta = {
        'abstract': True,
        'queryset_class': StormQuerySet,
        'id_prefix': None,
        'lookup_fields': ['id'],
    }

    def to_mongo(self, use_db_field=True, fields=None):
        if not fields or 'id' in fields:
            if self._data.get('id') is None:
                id_field = self._fields['id']
                self._data['id'] = id_field.generate(owner=self)
        return super().to_mongo(use_db_field=use_db_field, fields=fields)

    def __str__(self):
        return str(self.id)


class NameMixin:

    name = StringField(min_length=1, unique=True, null=True, sparse=True)

    meta = {
        'indexes': ['name'],
        'ordering': ['name'],
        'lookup_fields': ['name'],
    }

    def __str__(self):
        return self.name if self.name is not None else self.id


class TypeMixin:

    type = StringField(min_length=1, required=True)

    meta = {
        'indexes': ['type'],
        'ordering': ['type'],
    }
