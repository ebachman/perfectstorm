import traceback

from .base import Model, Collection
from .exceptions import StormJobError
from .fields import StringField, ListField, DictField
from .heartbeat import Heartbeat


__all__ = [
    'Agent',
    'Application',
    'Group',
    'Job',
    'Procedure',
    'Resource',
    'Subscription',
]


class Agent(Model):

    _path = 'v1/agents'

    type = StringField()
    name = StringField(null=True)
    status = StringField(default='offline')
    options = DictField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heartbeat = Heartbeat(self)


class Resource(Model):

    _path = 'v1/resources'

    type = StringField()
    names = ListField(StringField())
    owner = StringField()

    parent = StringField(null=True)
    cluster = StringField(null=True)
    host = StringField(null=True)
    image = StringField(null=True)

    status = StringField(default='unknown')
    health = StringField(default='unknown')

    snapshot = DictField(null=True)


class GroupMembersCollection(Collection):

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group

    def _replace(self, **kwargs):
        kwargs.setdefault('group', self.group)
        return super()._replace(**kwargs)

    @property
    def base_url(self):
        return self.group.url / 'members'

    def add(self, members):
        member_ids = [member.id for member in members]
        self._session.post(json={'include': member_ids})

    def remove(self, members):
        member_ids = [member.id for member in members]
        self._session.post(json={'exclude': member_ids})


class Group(Model):

    _path = 'v1/groups'

    name = StringField(null=True)

    query = DictField()
    services = ListField(DictField())

    include = ListField(StringField())
    exclude = ListField(StringField())

    def members(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        return GroupMembersCollection(
            group=self, model=Resource, query=query, session=self._session)


class Application(Model):

    _path = 'v1/apps'

    name = StringField(null=True)

    components = ListField(StringField())
    links = ListField(DictField())
    expose = ListField(DictField())


class Procedure(Model):

    _path = 'v1/procedures'

    type = StringField()
    name = StringField(null=True)

    content = StringField(blank=True, default='')
    options = DictField()
    params = DictField()

    def exec(self, target, options=None, params=None, wait=True):
        if options is None:
            options = {}
        if params is None:
            params = {}

        url = self.url / 'exec'
        data = {
            'target': target,
            'procedure': self.id,
            'options': options,
            'params': params,
        }

        data = self._session.post(url, json=data)
        job = Job(data, session=self._session)

        if wait:
            job.wait()
        return job

    def attach(self, group, target, options=None, params=None):
        if options is None:
            options = {}
        if params is None:
            params = {}

        url = self.url / 'attach'

        data = {
            'group': group,
            'target': target,
            'options': options,
            'params': params,
        }

        data = self._session.post(url, json=data)
        return Subscription(data, session=self._session)


class JobHandler:

    def __init__(self, job):
        self.job = job

    def __enter__(self):
        return self.job

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.job.is_complete():
            return

        if exc_value is None:
            self.job.complete()
        else:
            self.job.exception(exc_value)


class Job(Model):

    _path = 'v1/jobs'

    type = StringField()
    owner = StringField(null=True, read_only=True)

    target = StringField(null=True)
    procedure = StringField(null=True)

    content = StringField()
    options = DictField()
    params = DictField()

    status = StringField(read_only=True)
    result = DictField()

    created = StringField(null=True)

    def is_pending(self):
        return self.status == 'pending'

    def is_running(self):
        return self.status == 'running'

    def is_complete(self):
        return self.status in ('done', 'error')

    def get_procedure(self):
        procedure = Procedure.objects.get(self.procedure)

        if self.options or self.params:
            procedure = Procedure(
                content=procedure.content,
                options={**procedure.options, **self.options},
                params={**procedure.params, **self.params},
            )

        return procedure

    def handle(self, owner):
        url = self.url / 'handle'
        self._session.post(url, json={'owner': owner})
        self.reload()
        return JobHandler(self)

    def complete(self, result=None):
        if result is None:
            result = {}
        url = self.url / 'complete'
        self._session.post(url, json={'result': result})
        self.reload()

    def fail(self, result=None):
        if result is None:
            result = {}
        url = self.url / 'fail'
        self._session.post(url, json={'result': result})
        self.reload()

    def exception(self, exc):
        self.fail({
            'error': ''.join(traceback.format_exception(
                type(exc), exc, exc.__traceback__)),
        })

    def wait(self, delete=True, raise_on_error=True):
        from . import events

        event_filter = events.EventFilter([
            events.EventMask(
                event_type='updated', entity_type='job', entity_id=self.id),
            events.EventMask(
                event_type='deleted', entity_type='job', entity_id=self.id),
        ])

        with event_filter(events.stream()) as stream:
            while True:
                self.reload()
                if self.is_complete():
                    break
                next(stream)

        if delete:
            self.delete()

        if raise_on_error:
            self.raise_on_error()

    def raise_on_error(self):
        if self.status == 'error':
            raise StormJobError(self.id, job=self, details=self.result)


class Subscription(Model):

    _path = 'v1/subscriptions'

    group = StringField(null=True)
    procedure = StringField(null=True)

    target = StringField(null=True)
    options = DictField()
    params = DictField()
