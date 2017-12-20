import threading
import time
import traceback

from .. import exceptions
from .base import Resource, Collection, json_compact


def json_exception(exc_value):
    exc_type = type(exc_value)
    exc_tb = exc_value.__traceback__

    return {
        'type': '.'.join((exc_type.__module__, exc_type.__name__)),
        'exception': traceback.format_exception_only(exc_type, exc_value),
        'traceback': traceback.format_exception(exc_type, exc_value, exc_tb),
    }


class Group(Resource):

    class Meta:
        path = 'v1/groups/'
        lookup_field = 'name'

    def members(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        params = {'q': json_compact(query)}
        return self._get('members', params=params)

    def add_members(self, members):
        self._post('members', json={'include': list(members)})

    def remove_members(self, members):
        self._post('members', json={'exclude': list(members)})

    def set_members(self, members):
        wanted_members = list(members)
        current_members = [member['cloud_id'] for member in self.members()]
        unwanted_members = [member for member in current_members if member not in wanted_members]
        self._post('members', json={'include': list(wanted_members), 'exclude': list(unwanted_members)})


class Application(Resource):

    class Meta:
        path = 'v1/apps/'
        lookup_field = 'name'


class Recipe(Resource):

    class Meta:
        path = 'v1/recipes/'
        lookup_field = 'name'


class TriggerHeartbeatThread(threading.Thread):

    def __init__(self, trigger):
        super().__init__()
        self.trigger = trigger
        self._cancel_event = threading.Event()

    def run(self):
        trigger = self.trigger
        interval = trigger.heartbeat_interval
        event = self._cancel_event

        while not event.wait(interval):
            trigger.heartbeat()

    def cancel(self):
        self._cancel_event.set()


class TriggerHandler:

    def __init__(self, trigger):
        self.trigger = trigger
        self._thread = TriggerHeartbeatThread(self.trigger)

    def start_heartbeat(self):
        if self._thread is None:
            raise RuntimeError('handlers can only be used once')
        self._thread.start()

    def cancel_heartbeat(self):
        if self._thread is None:
            return
        self._thread.cancel()
        self._thread = None

    def __enter__(self):
        self.start_heartbeat()
        return self.trigger

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.cancel_heartbeat()

        if self.trigger.is_complete():
            return

        if exc_value is None:
            self.trigger.complete()
        else:
            self.trigger.fail(exc_value)


class TriggerCollection(Collection):

    def run(*args, **kwargs):
        if len(args) < 1:
            raise TypeError("run() missing 2 required positional-only arguments: 'self' and 'name'")
        if len(args) < 2:
            raise TypeError("run() missing 1 required positional-only argument: 'name'")
        self, name = args

        trigger = self.create(name=name, arguments=kwargs)
        trigger.wait()
        return trigger


class Trigger(Resource):

    heartbeat_interval = 30

    collection_class = TriggerCollection

    class Meta:
        path = 'v1/triggers/'
        lookup_field = 'uuid'

    def is_pending(self):
        return self['status'] == 'pending'

    def is_running(self):
        return self['status'] == 'running'

    def is_complete(self):
        return self['status'] in ('done', 'error')

    def is_error(self):
        return self['status'] == 'error'

    def handle(self):
        self._post('handle')
        self.refresh()
        return TriggerHandler(self)

    def heartbeat(self):
        self._post('heartbeat')

    def complete(self, result=None, status='done'):
        if result is None:
            result = {}

        self['status'] = status
        self['result'] = result

        self.patch(['status', 'result'])

    def fail(self, exception):
        result = {
            'exception': json_exception(exception),
        }
        self.complete(result, 'error')

    def wait(self, poll_interval=1, delete=True, raise_on_error=True):
        while not self.is_complete():
            time.sleep(poll_interval)
            self.refresh()

        if delete:
            self.delete()

        if raise_on_error:
            self.raise_on_error()

    def raise_on_error(self):
        if not self.is_error():
            return

        parent_exception = None
        exc_info = self['result'].get('exception')

        if exc_info:
            # If the trigger failed because of an exception,
            # emulate exception chaining.
            parent_exception = Exception(
                exc_info.get('type'),
                exc_info.get('exception'),
                exc_info.get('traceback'),
            )

        raise exceptions.TriggerError(self.identifier, trigger=self) from parent_exception
