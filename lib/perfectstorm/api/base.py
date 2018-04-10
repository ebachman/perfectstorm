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

import abc
import json
import threading

from ..exceptions import APINotFoundError, ObjectNotFound, MultipleObjectsReturned
from .session import current_session


def json_compact(*args, **kwargs):
    kwargs.setdefault('separators', (',', ':'))
    return json.dumps(*args, **kwargs)


class AbstractCollection(metaclass=abc.ABCMeta):

    def __init__(self, model):
        self.model = model

    @abc.abstractmethod
    def all(self):
        raise NotImplementedError

    @abc.abstractmethod
    def filter(self, *args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, *args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __len__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __getitem__(self, index):
        raise NotImplementedError

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.model.__name__)


class Collection(AbstractCollection):

    def __init__(self, model, query=None, session=None):
        super().__init__(model=model)
        self._query = query
        if session is None:
            session = current_session()
        self._session = session
        self._elems = None
        self._lock = threading.RLock()

    def _replace(self, **kwargs):
        kwargs.setdefault('model', self.model)
        kwargs.setdefault('query', self._query)
        kwargs.setdefault('session', self._session)
        return self.__class__(**kwargs)

    @property
    def base_url(self):
        return self._session.api_root / self.model._path

    @property
    def url(self):
        if self._query:
            params = {'q': json_compact(self._query)}
        else:
            params = {}
        return self.base_url.params(params)

    def all(self):
        return self._replace()

    def filter(self, *args, **kwargs):
        query = dict(*args, **kwargs)
        if not query:
            query = self._query
        elif self._query:
            query = {'$and': [self._query, query]}
        return self._replace(query=query)

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

            documents = self._session.get(self.url)
            self._elems = [self.model(doc, session=self._session) for doc in documents]

        return self._elems

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.model.__name__)


class EmptyCollection(AbstractCollection):

    def all(self):
        return self

    def filter(self, *args, **kwargs):
        return self

    def get(self, *args, **kwargs):
        raise ObjectNotFound

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0

    def __getitem__(self, index):
        if isinstance(index, slice):
            return []
        raise IndexError(index)


class Manager:

    def __init__(self, model, session=None):
        self.model = model
        self._session = session

    def _replace(self, **kwargs):
        kwargs.setdefault('model', self.model)
        kwargs.setdefault('session', self._session)
        return self.__class__(**kwargs)

    @property
    def url(self):
        session = self._session if self._session is not None else current_session()
        return session.api_root / self.model._path

    def none(self):
        return EmptyCollection(model=self.model)

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


class Model(metaclass=ModelMeta):

    def __init__(self, data=None, pk=None, session=None, **kwargs):
        super().__init__()

        non_field_kwargs = [key for key in kwargs if key not in self._fields]
        if non_field_kwargs:
            raise TypeError('__init__() got an unexpected keyword argument {!r}'.format(non_field_kwargs))

        if session is None:
            session = current_session()
        self._session = session

        self._data = {}

        if data is None:
            data = {}
        if kwargs:
            data = dict(data, **kwargs)

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
        return self.objects.url / object_id

    def reload(self, session=None):
        """Fetch the data from the API server for this object."""
        if session is None:
            session = self._session
        try:
            response_data = session.get(self.url)
        except APINotFoundError as exc:
            raise ObjectNotFound(self.pk)
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
        except APINotFoundError as exc:
            raise ObjectNotFound(self.pk)
        self._data = response_data

    def delete(self, session=None):
        """Delete this object from the API server."""
        if session is None:
            session = self._session

        try:
            session.delete(self.url)
        except APINotFoundError as exc:
            raise ObjectNotFound(self.pk)

    def validate(self, skip_fields=None):
        cls = self.__class__
        for name in self._fields:
            if skip_fields is not None and name in skip_fields:
                continue
            field = getattr(cls, name)
            if not field.read_only:
                value = getattr(self, name)
                field.validate(value)

    def __str__(self):
        return str(self.pk)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, str(self))
