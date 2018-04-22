import time
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
]


class Agent(Model):

    _path = 'v1/agents'

    type = StringField()
    name = StringField(null=True)
    status = StringField(default='offline')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heartbeat = Heartbeat(self)


class Resource(Model):

    _path = 'v1/resources'

    type = StringField()
    names = ListField(StringField())
    owner = StringField()

    image = StringField(null=True)
    parent = StringField(null=True)

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
        return GroupMembersCollection(group=self, model=Resource, query=query, session=self._session)


class Application(Model):

    _path = 'v1/apps'

    name = StringField(null=True)

    components = ListField(StringField())
    links = ListField(DictField())
    expose = ListField(DictField())


class ProcedureMixin(Model):

    content = StringField(null=True)
    options = DictField()
    params = DictField()
    target = StringField(null=True)


class Procedure(ProcedureMixin, Model):

    _path = 'v1/procedures'

    type = StringField()
    name = StringField(null=True)


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
            self.job.fail(exc_value)


class Job(ProcedureMixin, Model):

    _path = 'v1/jobs'

    type = StringField(null=True)
    owner = StringField(read_only=True)
    status = StringField(read_only=True)

    procedure = StringField(null=True)
    result = DictField()

    created = StringField(null=True)

    def is_pending(self):
        return self.status == 'pending'

    def is_running(self):
        return self.status == 'running'

    def is_complete(self):
        return self.status in ('done', 'error')

    def is_error(self):
        return self.status == 'error'

    def handle(self, owner):
        url = self.url / 'handle'
        self._session.post(url, json={'owner': owner.id})
        self.reload()
        return JobHandler(self)

    def complete(self, result=None, status='done'):
        if result is None:
            result = {}
        url = self.url / 'complete'
        self._session.post(url, json={'result': result})
        self.reload()

    def fail(self, exc):
        result = {
            'error': ''.join(traceback.format_exception(
                type(exc), exc, exc.__traceback__)),
        }

        url = self.url / 'fail'
        self._session.post(url, json={'result': result})
        self.reload()

    def wait(self, poll_interval=1, delete=True, raise_on_error=True):
        while True:
            self.reload()
            if self.is_complete():
                break
            time.sleep(poll_interval)

        if delete:
            self.delete()

        if raise_on_error:
            self.raise_on_error()

    def raise_on_error(self):
        if not self.is_error():
            return
        raise StormJobError(self.id, job=self, details=self.result)
