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
import uuid
from datetime import datetime, timedelta

from django.db import models

from jsonfield import JSONField

from mongoengine import (
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    IntField,
    ListField,
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


class Resource(Document):

    type = StringField(min_length=1, required=True)
    names = ListField(StringField(min_length=1), min_length=1, required=True)

    host = StringField(min_length=1, null=True)
    image = StringField(min_length=1, null=True)

    snapshot = EscapedDynamicField()

    meta = {
        'indexes': [
            'type',
            'names',
        ],
    }

    def __str__(self):
        return self.names[0] if self.names else str(self.pk)


class Service(EmbeddedDocument):

    PROTOCOL_CHOICES = (
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
    )

    name = StringField(min_length=1, required=True, unique=True)

    protocol = StringField(choices=PROTOCOL_CHOICES, required=True)
    port = IntField(required=True)

    def reference(self):
        return ServiceReference(group=self._instance, service_name=self.name)

    def __str__(self):
        return '{}[{}]'.format(self._instance, self.name)


class Group(Document):

    name = StringField(min_length=1, required=True, unique=True)
    services = EmbeddedDocumentListField(Service)

    query = EscapedDynamicField()
    include = ListField(ReferenceField(Resource))
    exclude = ListField(ReferenceField(Resource))

    meta = {
        'indexes': [
            'name',
        ],
    }

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

    def __str__(self):
        return self.name


class ServiceReference(EmbeddedDocument):

    group = ReferenceField(Group)
    service_name = StringField()

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

    from_component = ReferenceField(Group)
    to_service = EmbeddedDocumentField(ServiceReference)

    def clean(self):
        if self.from_component not in self._instance.components:
            raise ValidationError('Source component is not part of the application')
        if self.to_service.group not in self._instance.components:
            raise ValidationError('Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class Application(Document):

    name = StringField(min_length=1, required=True, unique=True)

    components = ListField(ReferenceField(Group))
    links = EmbeddedDocumentListField(ComponentLink)
    expose = EmbeddedDocumentListField(ServiceReference)

    meta = {
        'indexes': [
            'name',
        ],
    }

    def __str__(self):
        return self.name


class TriggerQuerySet(models.QuerySet):

    def stale(self):
        threshold = datetime.now() - Trigger.HEARTBEAT_DURATION
        return self.filter(status='running', heartbeat__lt=threshold)


class Trigger(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    HEARTBEAT_DURATION = timedelta(seconds=60)

    name = models.SlugField()
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')

    arguments = JSONField(default=dict)
    result = JSONField(default=dict)

    created = models.DateTimeField(auto_now_add=True)
    heartbeat = models.DateTimeField(auto_now_add=True)

    objects = TriggerQuerySet.as_manager()

    class Meta:
        ordering = ('created',)


class Recipe(models.Model):

    type = models.SlugField()
    name = models.SlugField(unique=True)
    content = models.TextField(default='')

    options = JSONField(default=dict)
    params = JSONField(default=dict)

    target_any_of = models.SlugField(null=True, db_index=False)
    target_all_in = models.SlugField(null=True, db_index=False)
    add_to = models.SlugField(null=True, db_index=False)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.type)
