import time
import traceback

from .base import Model, Collection
from .exceptions import StormTriggerError
from .fields import StringField, ListField, DictField
from .heartbeat import Heartbeat


__all__ = [
    'Agent',
    'Application',
    'Group',
    'Procedure',
    'Resource',
    'Trigger',
]


def json_exception(exc_value):
    exc_type = type(exc_value)
    exc_tb = exc_value.__traceback__

    return {
        'type': '.'.join((exc_type.__module__, exc_type.__name__)),
        'exception': traceback.format_exception_only(exc_type, exc_value),
        'traceback': traceback.format_exception(exc_type, exc_value, exc_tb),
    }


class Agent(Model):

    _path = 'v1/agents'

    type = StringField()

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


class TriggerHandler:

    def __init__(self, trigger):
        self.trigger = trigger

    def __enter__(self):
        return self.trigger

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.trigger.is_complete():
            return

        if exc_value is None:
            self.trigger.complete()
        else:
            self.trigger.fail(exc_value)


class Trigger(ProcedureMixin, Model):

    _path = 'v1/triggers'

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

    def handle(self, agent):
        url = self.url / 'handle'
        self._session.post(url, json={'agent': agent.id})
        self.reload()
        return TriggerHandler(self)

    def complete(self, result=None, status='done'):
        if result is None:
            result = {}
        url = self.url / 'complete'
        self._session.post(url, json={'result': result})
        self.reload()

    def fail(self, exception):
        url = self.url / 'fail'
        result = {'exception': json_exception(exception)}
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

        parent_exception = None
        exc_info = self.result.get('exception')

        if exc_info:
            # If the trigger failed because of an exception,
            # emulate exception chaining.
            parent_exception = Exception(
                exc_info.get('type'),
                exc_info.get('exception'),
                exc_info.get('traceback'),
            )

        raise StormTriggerError(self.id, trigger=self) from parent_exception
