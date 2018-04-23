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
    signals,
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


_cleanup_interval = 1
_cleanup_timestamp = 0


def cleanup_expired_agents():
    global _cleanup_timestamp
    now = time.time()
    if now - _cleanup_timestamp < _cleanup_interval:
        return
    Agent.objects.expired().update(status='offline')
    _cleanup_timestamp = time.time()


def cleanup_owned_documents(deleted_agent_ids):
    if not deleted_agent_ids:
        return

    orphaned_resources = Resource.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_resources.delete()

    orphaned_jobs = Job.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_jobs.update(status='pending', owner=None)


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
        self._document_type = document_type
        super().__init__(**kwargs)

    @property
    def document_type(self):
        if isinstance(self._document_type, str):
            self._document_type = globals()[self._document_type]
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


class Agent(NameMixin, TypeMixin, StormDocument):

    HEARTBEAT_DURATION = timedelta(seconds=60)

    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
    )

    heartbeat = DateTimeField(default=datetime.now, required=True)

    status = StringField(
        choices=STATUS_CHOICES, default='offline', required=True)
    options = EscapedDictField()

    meta = {
        'id_prefix': 'agt-',
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

    parent = StormReferenceField('Resource', null=True)
    image = StringField(min_length=1, null=True)

    status = StringField(
        choices=STATUS_CHOICES, default='unknown', required=True)
    health = StringField(
        choices=HEALTH_CHOICES, default='unknown', required=True)

    snapshot = EscapedDictField()

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

    query = EscapedDictField(required=True)
    include = ListField(StormReferenceField(Resource))
    exclude = ListField(StormReferenceField(Resource))

    meta = {
        'id_prefix': 'grp-',
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
                'Service {} is not provided by group {}'.format(
                    self.service_name, self.group.name))

    def __str__(self):
        return str(self.service)


class ComponentLink(EmbeddedDocument):

    from_component = StormReferenceField(Group, required=True)
    to_service = EmbeddedDocumentField(ServiceReference, required=True)

    def clean(self):
        if self.from_component not in self._instance.components:
            raise ValidationError(
                'Source component is not part of the application')
        if self.to_service.group not in self._instance.components:
            raise ValidationError(
                'Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class Application(NameMixin, StormDocument):

    components = ListField(StormReferenceField(Group))
    links = EmbeddedDocumentListField(ComponentLink)
    expose = EmbeddedDocumentListField(ServiceReference)

    meta = {
        'id_prefix': 'app-',
    }


class Procedure(NameMixin, TypeMixin, StormDocument):

    content = EscapedDictField()
    options = EscapedDictField()
    params = EscapedDictField()

    meta = {
        'id_prefix': 'prc-',
    }


class Job(StormDocument):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    owner = StormReferenceField(Agent, null=True)

    target = StormReferenceField(Resource)
    procedure = StormReferenceField(Procedure)
    options = EscapedDictField()
    params = EscapedDictField()

    status = StringField(
        choices=STATUS_CHOICES, default='pending', required=True)
    result = EscapedDictField(required=True)

    created = DateTimeField(default=datetime.now, required=True)

    meta = {
        'id_prefix': 'job-',
        'indexes': [
            'created',
            'owner',
        ],
        'ordering': ['created'],
    }

    def __str__(self):
        return str(self.pk)


class Event(Document):

    MAX_EVENTS = 10000

    EVENT_TYPE_CHOICES = [
        'created',
        'updated',
        'deleted',
    ]

    id = AutoIncrementField(primary_key=True)
    date = DateTimeField(default=datetime.now)

    event_type = StringField(choices=EVENT_TYPE_CHOICES, required=True)
    entity_type = StringField(required=True)
    entity_id = StringField(required=True)
    entity_names = ListField(StringField())

    meta = {
        'ordering': ['id'],
        'max_documents': MAX_EVENTS,
        'max_size': 8 * 1024 * MAX_EVENTS,
    }

    @staticmethod
    def record_event(event_type, obj):
        if not isinstance(obj, StormDocument):
            return

        names = []
        if isinstance(obj, NameMixin):
            if obj.name is not None:
                names.append(obj.name)
        elif isinstance(obj, Resource):
            names.extend(obj.names)

        ev = Event(
            event_type=event_type,
            entity_type=type(obj).__name__.lower(),
            entity_id=obj.id,
            entity_names=names,
        )

        ev.save()
        return ev


def on_save(sender, document, created=False, **kwargs):
    event_type = 'created' if created else 'updated'
    Event.record_event(event_type, document)


def on_delete(sender, document, **kwargs):
    Event.record_event('deleted', document)


signals.post_save.connect(on_save)
signals.post_delete.connect(on_delete)
