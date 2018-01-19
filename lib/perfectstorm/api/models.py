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

import time
import traceback

from ..exceptions import TriggerError
from .base import Model, Collection
from .fields import StringField, ListField, DictField
from .heartbeat import Heartbeat


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

    id = StringField(primary_key=True)
    type = StringField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heartbeat = Heartbeat(self)


class Resource(Model):

    _path = 'v1/resources'

    id = StringField(primary_key=True)
    type = StringField()
    names = ListField(StringField(), primary_key=True)

    owner = StringField()
    image = StringField(null=True)
    host = StringField(null=True)
    snapshot = DictField(null=True)


class GroupMembersCollection(Collection):

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group

    @property
    def url(self):
        return self.group.url / 'members'

    def add(self, members):
        member_ids = [member.id for member in members]
        self._session.post(json={'include': member_ids})

    def remove(self, members):
        member_ids = [member.id for member in members]
        self._session.post(json={'exclude': member_ids})


class Group(Model):

    _path = 'v1/groups'

    id = StringField(primary_key=True)
    name = StringField(primary_key=True)

    query = DictField()
    services = ListField(DictField())

    include = ListField(StringField())
    exclude = ListField(StringField())

    def members(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        return GroupMembersCollection(group=self, model=Resource, query=query, session=self._session)


class Application(Model):

    _path = 'v1/apps'

    id = StringField(primary_key=True)
    name = StringField(primary_key=True)

    components = ListField(StringField())
    links = DictField()
    expose = ListField(StringField())


class Recipe(Model):

    _path = 'v1/recipes'

    id = StringField(primary_key=True)
    name = StringField(primary_key=True)
    type = StringField()

    content = StringField()
    options = DictField()
    params = DictField()

    target = StringField(null=True)


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


class Trigger(Model):

    _path = 'v1/triggers'

    id = StringField(primary_key=True)
    type = StringField()
    status = StringField(default='pending')

    arguments = DictField()
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

        raise TriggerError(self.pk, trigger=self) from parent_exception
