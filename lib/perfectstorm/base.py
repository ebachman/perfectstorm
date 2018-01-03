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

import json
import threading
from urllib.parse import quote, urljoin

import requests
from requests import HTTPError

from .exceptions import ObjectNotFound, MultipleObjectsReturned


_local = threading.local()


def appendslash(url):
    return url if url.endswith('/') else url + '/'


def json_compact(*args, **kwargs):
    kwargs.setdefault('separators', (',', ':'))
    return json.dumps(*args, **kwargs)


def current_session():
    try:
        return _local.session_stack[-1]
    except (AttributeError, IndexError):
        raise RuntimeError('No active session found')


class Session:

    def __init__(self, host, port):
        self.api_root = 'http://%s:%d/' % (quote(host), port)

    def request(self, method, path, **kwargs):
        url = appendslash(urljoin(self.api_root, path))

        if not url.startswith(self.api_root):
            raise RuntimeError('URL has been mangled: %r' % url)

        response = requests.request(method, url, **kwargs)
        response.raise_for_status()

        if response.status_code != 204:
            return response.json()

    def get(self, url, **kwargs):
        return self.request('get', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('post', url, **kwargs)

    def put(self, url, **kwargs):
        return self.request('put', url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request('patch', url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('delete', url, **kwargs)

    def __enter__(self):
        try:
            stack = _local.session_stack
        except AttributeError:
            stack = _local.session_stack = []
        stack.append(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        popped = _local.session_stack.pop(-1)
        assert popped is self


class Collection:

    def __init__(self, model, query=None, session=None):
        self.model = model
        self.query = query
        if session is None:
            session = current_session()
        self.session = session
        self._elems = None
        self._lock = threading.RLock()

    def all(self):
        return self.__class__(model=self.model, query=self.query, session=self.session)

    def filter(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        if not query:
            query = self.query
        elif self.query:
            query = {'$and': [self.query, query]}
        return self.__class__(model=self.model, query=query, session=self.session)

    def __iter__(self):
        if self._elems is None:
            with self._lock:
                if self._elems is None:
                    self._elems = self._retrieve()
        return iter(self._elems)

    def _retrieve(self):
        if self.query:
            params = {'q': json_compact(self.query)}
        else:
            params = None
        documents = self.session.get(self.model.Meta.path, params=params)
        return [self.model(doc, session=self.session) for doc in documents]

    def get(self, *args, **kwargs):
        query = dict(*args, **kwargs)

        if query:
            it = iter(self.filter(query))
        else:
            it = iter(self)

        try:
            obj = next(it)
        except StopIteration:
            raise ObjectNotFound('%s matching query does not exist' % self.model.__name__)

        try:
            next(it)
        except StopIteration:
            pass
        else:
            raise MultipleObjectsReturned('Multiple objects returned instead of 1')

        return obj

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.model.__name__)


class Manager:

    def __init__(self, model, session=None):
        self.model = model
        self.session = session

    @property
    def url(self):
        session = self.session if self.session is not None else current_session()
        return urljoin(session.api_root, self.model.Meta.path)

    def all(self):
        return Collection(model=self.model, session=self.session)

    def filter(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        return Collection(model=self.model, query=query, session=self.session)

    def get(self, *args, **kwargs):
        return self.filter(*args, **kwargs).get()

    def get_or_create(self, *args, defaults=None, **kwargs):
        data = dict(*args, **kwargs)

        try:
            # TODO escape query
            obj = self.get(data)
            created = False
        except ObjectNotFound:
            if defaults is not None:
                data.update(defaults)
            obj = self.model(**data)
            obj.save()
            created = True

        return obj, created

    def update_or_create(self, *args, defaults=None, **kwargs):
        data = dict(*args, **kwargs)

        try:
            # TODO escape query
            obj = self.get(data)
            created = False
        except ObjectNotFound:
            obj = self.model(**defaults)
            created = True

        for key, value in data.items():
            setattr(obj, key, value)
        obj.save()

        return obj, created


class ModelMeta(type):

    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)
        cls.objects = Manager(cls)
        return cls


class Model(metaclass=ModelMeta):

    def __init__(self, *args, session=None, **kwargs):
        self.__dict__['_data'] = dict(*args, **kwargs)
        if session is None:
            session = current_session()
        self.__dict__['session'] = session

    @property
    def id(self):
        """Return the identifier that should be used in URLs."""
        object_id = self._data.get(self.Meta.id_field)

        if isinstance(object_id, (tuple, list)):
            # Pick the first element of lists
            object_id = object_id[0] if object_id else None
        elif isinstance(object_id, dict):
            raise TypeError('Unsupported ID field type: %s' % type(object_id).__name__)

        return object_id

    @property
    def url(self):
        object_id = self.id
        if object_id is None:
            raise AttributeError('No ID has been set')
        return urljoin(self.objects.url, quote(object_id))

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        self._data[name] = value

    def __delattr__(self, name):
        try:
            del self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def refresh(self):
        """Fetch the data from the API server for this object."""
        try:
            response_data = self.session.get(self.url)
        except HTTPError as exc:
            if exc.status_code == 404:
                raise ObjectNotFound(self.id)
            raise
        self._data = response_data

    def save(self):
        """
        Store the object on the API server. This will either create a new
        entity or update an existing one, depending on whether this object has
        an ID or not.
        """
        if self.id is not None:
            # If an ID is defined, try to update
            try:
                self._update()
            except ObjectNotFound:
                pass
            else:
                return

        # Either an ID is not defined, or the update returned 404
        self._create()

    def _create(self):
        response_data = self.session.post(self.objects.url, json=self._data)
        self._data = response_data

    def _update(self):
        try:
            response_data = self.session.put(self.url, json=self._data)
        except HTTPError as exc:
            if exc.response.status_code == 404:
                raise ObjectNotFound(self.id)
            raise
        self._data = response_data

    def delete(self):
        """Delete this object from the API server."""
        try:
            self.session.delete(self.url)
        except HTTPError as exc:
            if exc.response.status_code == 404:
                raise ObjectNotFound(self.id)
            raise

    def __str__(self):
        return str(self.id)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, str(self))
