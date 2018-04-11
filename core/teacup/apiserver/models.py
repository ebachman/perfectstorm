# Copyright (c) 2017, Composure.ai
# Copyright (c) 2018, Andrea Corbellini
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

import functools
import re
import time
import uuid
from datetime import datetime, timedelta

from mongoengine import (
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    IntField,
    ListField,
    QuerySet,
    StringField,
    ValidationError,
)

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


class EscapedDynamicField(BaseField):
    r"""
    A DynamicField-like field that allows any kind of keys in dictionaries.

    Specifically, it allows any key starting with '_', it does not treat
    any keys in a special way (such as '_cls') and transparently escapes
    forbidden BSON characters ('\0', '$' and '.') before saving.
    """

    def to_mongo(self, value, *args, **kwargs):
        return escape_keys(value)

    def to_python(self, value):
        return unescape_keys(value)

    def lookup_member(self, member_name):
        return member_name

    def prepare_query_value(self, op, value):
        if isinstance(value, str):
            return StringField().prepare_query_value(op, value)
        return super().prepare_query_value(op, self.to_mongo(value))


_cleanup_interval = 1
_cleanup_timestamp = 0


def cleanup_expired_agents():
    global _cleanup_timestamp
    now = time.time()
    if now - _cleanup_timestamp < _cleanup_interval:
        return
    Agent.objects.expired().delete()
    _cleanup_timestamp = time.time()


def cleanup_owned_documents(deleted_agent_ids):
    if not deleted_agent_ids:
        return

    orphaned_resources = Resource.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_resources.delete()

    orphaned_triggers = Trigger.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_triggers.filter(status='running').update(status='pending')
    orphaned_triggers.update(owner=None)


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

    def __init__(self, document_type, **kwargs):
        self.document_type = document_type
        super().__init__(**kwargs)

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


class StormQuerySet(QuerySet):

    def lookup(self, value):
        lookup_fields = self._document._meta['lookup_fields']

        if value is None or not lookup_fields:
            raise self.DoesNotExist('{} matching query does not exist.'.format(self.__class__._meta.object_name))

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
        'lookup_fields': ['name'],
    }

    def __str__(self):
        return self.name if self.name is not None else self.id


class TypeMixin:

    type = StringField(min_length=1, required=True)

    meta = {
        'indexes': ['type'],
    }


class AgentQuerySet(StormQuerySet):

    def expired(self):
        threshold = datetime.now() - Agent.HEARTBEAT_DURATION
        return self.filter(heartbeat__lt=threshold)

    def delete(self, *args, **kwargs):
        queryset = self.clone()
        agent_ids = list(queryset.values_list('pk'))
        cleanup_owned_documents(agent_ids)

        super().delete(*args, **kwargs)


class Agent(TypeMixin, StormDocument):

    HEARTBEAT_DURATION = timedelta(seconds=60)

    heartbeat = DateTimeField(default=datetime.now, required=True)

    meta = {
        'id_prefix': 'agent-',
        'queryset_class': AgentQuerySet,
        'indexes': ['heartbeat'],
    }

    def delete(self):
        cleanup_owned_documents([self.pk])
        super().delete()


class Resource(TypeMixin, StormDocument):

    STATUS_CHOICES = (
        ('unknown', 'Unknown'),
        ('creating', 'Creating'),
        ('created', 'Created'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('updating', 'Updating'),
        ('updated', 'Updated'),
        ('stopping', 'Stopped'),
        ('stopped', 'Stopped'),
        ('removing', 'Removing'),
        ('error', 'Error'),
    )

    HEALTH_CHOICES = (
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
    )

    names = ListField(StringField(min_length=1))
    owner = StormReferenceField(Agent, required=True)

    parent = StringField(min_length=1, null=True)
    image = StringField(min_length=1, null=True)

    status = StringField(choices=STATUS_CHOICES, default='unknown', required=True)
    health = StringField(choices=HEALTH_CHOICES, default='unknown', required=True)

    snapshot = EscapedDynamicField()

    meta = {
        'id_prefix': 'res-',
        'indexes': [
            'names',
            'owner',
            'status',
            'health',
        ],
        'lookup_fields': ['names'],
    }

    def __str__(self):
        return self.names[0] if self.names else str(self.pk)


class Service(NameMixin, EmbeddedDocument):

    PROTOCOL_CHOICES = (
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
    )

    protocol = StringField(choices=PROTOCOL_CHOICES, required=True)
    port = IntField(required=True)

    def to_reference(self):
        return ServiceReference(group=self._instance, service_name=self.name)

    def __str__(self):
        return '{}[{}]'.format(self._instance, self.name)


class Group(NameMixin, StormDocument):

    services = EmbeddedDocumentListField(Service)

    query = EscapedDynamicField(default=dict, required=True)
    include = ListField(StormReferenceField(Resource))
    exclude = ListField(StormReferenceField(Resource))

    meta = {
        'id_prefix': 'group-',
    }

    def members(self, filter=None):
        query = self.query

        if self.include:
            cond = {'_id': {'$in': self.include}}

            if query:
                query = {'$or': [query, cond]}
            else:
                query = cond

        if self.exclude:
            cond = {'_id': {'$nin': self.exclude}}

            if query:
                query = {'$and': [query, cond]}
            else:
                query = cond

        if query and filter:
            query = {'$and': [query, filter]}

        if query:
            return Resource.objects(__raw__=query)
        else:
            return Resource.objects.none()


class ServiceReference(EmbeddedDocument):

    group = StormReferenceField(Group, required=True)
    service_name = StringField(min_length=1, required=True)

    @property
    def service(self):
        return self.group.services.get(name=self.service_name)

    def clean(self):
        available_service_names = [
            service.name for service in self.group.services]
        if self.service_name not in available_service_names:
            raise ValidationError(
                'Service {} is not provided by group {}'.format(self.service_name, self.group.name))

    def __str__(self):
        return str(self.service)


class ComponentLink(EmbeddedDocument):

    from_component = StormReferenceField(Group, required=True)
    to_service = EmbeddedDocumentField(ServiceReference, required=True)

    def clean(self):
        if self.from_component not in self._instance.components:
            raise ValidationError('Source component is not part of the application')
        if self.to_service.group not in self._instance.components:
            raise ValidationError('Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class Application(NameMixin, StormDocument):

    components = ListField(StormReferenceField(Group))
    links = EmbeddedDocumentListField(ComponentLink)
    expose = EmbeddedDocumentListField(ServiceReference)

    meta = {
        'id_prefix': 'app-',
    }


class ProcedureMixin:

    content = StringField(null=True)
    options = EscapedDynamicField(default=dict)
    params = EscapedDynamicField(default=dict)
    target = StormReferenceField(Resource, null=True)


class Procedure(NameMixin, TypeMixin, ProcedureMixin, StormDocument):

    content = StringField(required=True)

    meta = {
        'id_prefix': 'proc-',
    }


class Trigger(TypeMixin, ProcedureMixin, StormDocument):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    owner = StormReferenceField(Agent, null=True)
    status = StringField(choices=STATUS_CHOICES, default='pending', required=True)

    type = StringField(min_length=1, null=True)
    procedure = StormReferenceField(Procedure, null=True)
    result = EscapedDynamicField(default=dict, required=True)

    created = DateTimeField(default=datetime.now, required=True)

    meta = {
        'id_prefix': 'trig-',
        'indexes': [
            'created',
            'owner',
        ],
        'ordering': ['created'],
    }

    def clean(self):
        super().clean()

        if not self.target:
            if not self.procedure or not self.procedure.target:
                raise ValidationError('No target specified')
            self.target = self.procedure.target

        if not self.content:
            if not self.procedure:
                raise ValidationError('No content and no procedure specified')

        if self.status not in ('done', 'error'):
            self.result = {}

    def __str__(self):
        return str(self.pk)
