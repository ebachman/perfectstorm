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

import threading
import time
import traceback

from .. import exceptions
from . import base


def json_exception(exc_value):
    exc_type = type(exc_value)
    exc_tb = exc_value.__traceback__

    return {
        'type': '.'.join((exc_type.__module__, exc_type.__name__)),
        'exception': traceback.format_exception_only(exc_type, exc_value),
        'traceback': traceback.format_exception(exc_type, exc_value, exc_tb),
    }


class Resource(base.Resource):

    class Meta:
        path = 'v1/resources/'
        lookup_field = None

    @property
    def identifier(self):
        return self['names'][0]


class Group(base.Resource):

    class Meta:
        path = 'v1/groups/'
        lookup_field = 'name'

    def members(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        params = {'q': base.json_compact(query)}
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


class Application(base.Resource):

    class Meta:
        path = 'v1/apps/'
        lookup_field = 'name'


class Recipe(base.Resource):

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


class TriggerCollection(base.Collection):

    def run(*args, **kwargs):
        if len(args) < 1:
            raise TypeError("run() missing 2 required positional-only arguments: 'self' and 'name'")
        if len(args) < 2:
            raise TypeError("run() missing 1 required positional-only argument: 'name'")
        self, name = args

        trigger = self.create(name=name, arguments=kwargs)
        trigger.wait()
        return trigger


class Trigger(base.Resource):

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
