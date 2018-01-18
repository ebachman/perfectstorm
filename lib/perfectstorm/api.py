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

from .exceptions import ValidationError, ObjectNotFound, MultipleObjectsReturned


_lock = threading.RLock()
_global_session = None
_local_sessions = threading.local()

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8000


def appendslash(url):
    return url if url.endswith('/') else url + '/'


def json_compact(*args, **kwargs):
    kwargs.setdefault('separators', (',', ':'))
    return json.dumps(*args, **kwargs)


def current_session():
    try:
        return _local_sessions.session_stack[-1]
    except (AttributeError, IndexError):
        pass

    session = _global_session
    if session is not None:
        return session

    raise RuntimeError('No active connections found. You must call connect() or use a Session object in a context manager')


def connect(host=None, port=None):
    global _global_session
    session = Session(host, port)
    with _lock:
        _global_session = session
    return session


class Session:

    def __init__(self, host=None, port=None):
        if host is None:
            host = DEFAULT_HOST
        if port is None:
            port = DEFAULT_PORT
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
            stack = _local_sessions.session_stack
        except AttributeError:
            stack = _local_sessions.session_stack = []
        stack.append(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        popped = _local_sessions.session_stack.pop(-1)
        assert popped is self


class Collection:

    def __init__(self, model, query=None, session=None):
        self.model = model
        self.query = query
        if session is None:
            session = current_session()
        self._session = session
        self._elems = None
        self._lock = threading.RLock()

    def all(self):
        return self.__class__(model=self.model, query=self.query, session=self._session)

    def filter(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        if not query:
            query = self.query
        elif self.query:
            query = {'$and': [self.query, query]}
        return self.__class__(model=self.model, query=query, session=self._session)

    def __iter__(self):
        self._retrieve()
        return iter(self._elems)

    def __len__(self):
        self._retrieve()
        return len(self._elems)

    def __getitem__(self, index):
        self._retrieve()
        return self._elems[index]

    def _retrieve(self):
        if self._elems is not None:
            return self._elems

        with self._lock:
            if self._elems is not None:
                return self._elems

            if self.query:
                params = {'q': json_compact(self.query)}
            else:
                params = None
            documents = self._session.get(self.model.Meta.path, params=params)
            self._elems = [self.model(doc, session=self._session) for doc in documents]

        return self._elems

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
        self._session = session

    def __call__(self, session=None):
        if session is None:
            session = self._session
        return self.__class__(model=self.model, session=session)

    @property
    def url(self):
        session = self._session if self._session is not None else current_session()
        return urljoin(session.api_root, self.model.Meta.path)

    def all(self):
        return Collection(model=self.model, session=self._session)

    def filter(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        return Collection(model=self.model, query=query, session=self._session)

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

    def __new__(mcls, name, bases, attrs, **kwargs):
        for attr in ('_fields', '_primary_keys'):
            if attr in attrs:
                raise TypeError('Reserved attribute: %r' % attr)
            value = []
            for base in reversed(bases):
                value.extend(getattr(base, attr, []))
            attrs[attr] = value

        cls = super().__new__(mcls, name, bases, attrs, **kwargs)
        cls.objects = Manager(cls)

        return cls


class Field:

    def __init__(self, *, primary_key=False, null=False, default=None):
        self.primary_key = primary_key
        self.null = null
        self.default = default

        if self.primary_key:
            # Primary keys can be omitted, in which case
            # a primary key will be generated by the server
            self.null = True

    def __set_name__(self, owner, name):
        self.name = name
        owner._fields.append(name)
        if self.primary_key:
            owner._primary_keys.append(name)

    def __get__(self, instance, owner):
        if instance is None:
            # This field is being accessed from the model class
            return self

        # Field accessed from a model instance
        value = instance._data.get(self.name)
        if value is None:
            if callable(self.default):
                value = self.default()
            else:
                value = self.default
            instance._data[self.name] = value
        return value

    def __set__(self, instance, value):
        instance._data[self.name] = value

    def validate(self, value):
        if value is None and not self.null:
            raise ValidationError('field cannot be None', field=self.name)


class StringField(Field):

    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, str):
            raise ValidationError('expected a string, got %r' % value, field=self.name)


class IntField(Field):

    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, int):
            raise ValidationError('expected an integer, got %r' % value, field=self.name)


class ListField(Field):

    def __init__(self, subfield, **kwargs):
        kwargs.setdefault('default', list)
        super().__init__(**kwargs)
        self.subfield = subfield

    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, (tuple, list)):
                raise ValidationError('expected a list or tuple, got %r' % value, field=self.name)
            for item in value:
                self.subfield.validate(item)


class DictField(Field):

    def __init__(self, **kwargs):
        kwargs.setdefault('default', dict)
        super().__init__(**kwargs)

    def validate(self, value):
        super().validate(value)

        visited = set()

        def validate_inner(obj):
            if obj is None or isinstance(obj, (str, int, float)):
                return
            if id(obj) in visited:
                raise ValidationError('object has circular references', field=self.name)
            visited.add(id(obj))
            if isinstance(obj, (tuple, list)):
                for item in obj:
                    validate_inner(item)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    if not isinstance(key, str):
                        raise ValidationError('dictionary keys must be strings, found %r' % key, field=self.name)
                    validate_inner(value)
            else:
                raise ValidationError('unknown type: %r' % obj, field=self.name)
            visited.remove(id(obj))

        validate_inner(value)


class Model(metaclass=ModelMeta):

    def __init__(self, data=None, pk=None, session=None, **kwargs):
        super().__init__()

        if data is None:
            data = {}
        if kwargs:
            data = dict(data, **kwargs)

        non_field_kwargs = [key for key in data if key not in self._fields]
        if non_field_kwargs:
            raise TypeError('Keys do not map to fields: %r' % non_field_kwargs)

        if session is None:
            session = current_session()
        self._session = session

        self._data = {}

        for key, value in data.items():
            if key in self._fields:
                setattr(self, key, value)

        if pk is not None:
            if not self._primary_keys:
                raise TypeError('No primary key fields defined')
            name = self._primary_keys[0]
            setattr(self, name, pk)

    @property
    def pk(self):
        for name in self._primary_keys:
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, (list, tuple)):
                    if value:
                        return value[0]
                else:
                    return value
        return None

    @property
    def url(self):
        object_id = self.pk
        if object_id is None:
            raise AttributeError('No ID has been set')
        return urljoin(self.objects.url, quote(object_id))

    def reload(self, session):
        """Fetch the data from the API server for this object."""
        if session is None:
            session = self._session
        try:
            response_data = session.get(self.url)
        except HTTPError as exc:
            if exc.status_code == 404:
                raise ObjectNotFound(self.pk)
            raise
        self._data = response_data

    def save(self, validate=True, session=None):
        """
        Store the object on the API server. This will either create a new
        entity or update an existing one, depending on whether this object has
        an ID or not.
        """
        if validate:
            self.validate()

        if session is None:
            session = self._session

        if self.pk is not None:
            # If an ID is defined, try to update
            try:
                self._update(session)
            except ObjectNotFound:
                pass
            else:
                return

        # Either an ID is not defined, or the update returned 404
        self._create(session)

    def _create(self, session):
        response_data = session.post(self.objects.url, json=self._data)
        self._data = response_data

    def _update(self, session):
        try:
            response_data = session.put(self.url, json=self._data)
        except HTTPError as exc:
            if exc.response.status_code == 404:
                raise ObjectNotFound(self.pk)
            raise
        self._data = response_data

    def delete(self, session=None):
        """Delete this object from the API server."""
        if session is None:
            session = self._session

        try:
            session.delete(self.url)
        except HTTPError as exc:
            if exc.response.status_code == 404:
                raise ObjectNotFound(self.pk)
            raise

    def validate(self, skip_fields=None):
        cls = self.__class__
        for name in self._fields:
            if skip_fields is not None and name in skip_fields:
                continue
            field = getattr(cls, name)
            value = getattr(self, name)
            field.validate(value)

    def __str__(self):
        return str(self.pk)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, str(self))
