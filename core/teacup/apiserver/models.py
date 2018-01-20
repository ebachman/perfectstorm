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
    ReferenceField,
    StringField,
    ValidationError,
)

from mongoengine.fields import BaseField


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
    orphaned_resources = Resource.objects.filter(owner__in=deleted_agent_ids)
    orphaned_resources.delete()

    orphaned_triggers = Trigger.objects.filter(owner__in=deleted_agent_ids)
    orphaned_triggers.filter(status='running').update(status='pending')
    orphaned_triggers.update(owner=None)


class FancyIdField(StringField):

    def __init__(self, prefix, *args, **kwargs):
        self.prefix = prefix
        super().__init__(*args, required=True, primary_key=True, null=False, default=self._generate_new, **kwargs)

    def _generate_new(self):
        return '-'.join((self.prefix, uuid.uuid1().hex))


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


class NameMixin:

    name = StringField(min_length=1, unique=True, required=True)

    meta = {
        'indexes': ['name'],
    }

    def __str__(self):
        return self.name


class TypeMixin:

    type = StringField(min_length=1, required=True)

    meta = {
        'indexes': ['type'],
    }


class AgentQuerySet(QuerySet):

    def expired(self):
        threshold = datetime.now() - Agent.HEARTBEAT_DURATION
        return self.filter(heartbeat__lt=threshold)

    def delete(self, *args, **kwargs):
        queryset = self.clone()
        agent_ids = list(queryset.values_list('pk'))
        super().delete(*args, **kwargs)
        cleanup_owned_documents(agent_ids)


class Agent(TypeMixin, Document):

    HEARTBEAT_DURATION = timedelta(seconds=60)

    id = FancyIdField('agent')
    heartbeat = DateTimeField(default=datetime.now, required=True)

    meta = {
        'queryset_class': AgentQuerySet,
        'indexes': ['heartbeat'],
    }

    def delete(self):
        super().delete()
        cleanup_owned_documents([self.pk])

    def __str__(self):
        return str(self.pk)


class Resource(TypeMixin, Document):

    id = FancyIdField('resource')
    names = ListField(StringField(min_length=1), min_length=1, required=True)
    owner = ReferenceField(Agent, required=True)

    parent = StringField(min_length=1, null=True)
    image = StringField(min_length=1, null=True)

    snapshot = EscapedDynamicField()

    meta = {
        'indexes': [
            'names',
            'owner',
        ],
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


class Group(NameMixin, Document):

    id = FancyIdField('group')
    name = StringField(min_length=1, required=True, unique=True)
    services = EmbeddedDocumentListField(Service)

    query = EscapedDynamicField(default=dict, required=True)
    include = ListField(ReferenceField(Resource))
    exclude = ListField(ReferenceField(Resource))

    def save(self, *args, write_concern=None, **kwargs):
        if write_concern is None:
            write_concern = {'w': 1, 'check_keys': False}
        return super().save(*args, write_concern=write_concern, **kwargs)

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

    group = ReferenceField(Group, required=True)
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

    from_component = ReferenceField(Group, required=True)
    to_service = EmbeddedDocumentField(ServiceReference, required=True)

    def clean(self):
        if self.from_component not in self._instance.components:
            raise ValidationError('Source component is not part of the application')
        if self.to_service.group not in self._instance.components:
            raise ValidationError('Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class Application(NameMixin, Document):

    id = FancyIdField('app')
    components = ListField(ReferenceField(Group))
    links = EmbeddedDocumentListField(ComponentLink)
    expose = EmbeddedDocumentListField(ServiceReference)


class Trigger(TypeMixin, Document):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    id = FancyIdField('recipe')
    status = StringField(choices=STATUS_CHOICES, default='pending', required=True)
    owner = ReferenceField(Agent, null=True)

    arguments = EscapedDynamicField(default=dict, required=True)
    result = EscapedDynamicField(default=dict, required=True)

    created = DateTimeField(default=datetime.now, required=True)

    meta = {
        'indexes': [
            'created',
            'owner',
        ],
        'ordering': ['created'],
    }

    def __str__(self):
        return str(self.pk)


class Recipe(NameMixin, TypeMixin, Document):

    id = FancyIdField('recipe')
    content = StringField(required=True)

    options = EscapedDynamicField(default=dict, required=True)
    params = EscapedDynamicField(default=dict, required=True)

    target = ReferenceField(Resource, null=True)

    meta = {
        'indexes': ['target'],
    }
