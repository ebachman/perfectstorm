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

import functools
import json
from urllib.parse import quote, urljoin

import requests

from .. import exceptions


def appendslash(url):
    return url if url.endswith('/') else url + '/'


def json_compact(*args, **kwargs):
    kwargs.setdefault('separators', (',', ':'))
    return json.dumps(*args, **kwargs)


def convert_exception(exc):
    if exc.response.status_code == 400:
        exc_type = exceptions.BadRequestError
        exc_args = (exc.response.json(),)
    elif exc.response.status_code == 404:
        exc_type = exceptions.NotFoundError
        exc_args = (exc.request.url,)
    else:
        exc_type = exceptions.PerfectStormHttpError
        exc_args = exc.args

    return exc_type(*exc_args, request=exc.request, response=exc.response)


def wrap_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as exc:
            raise convert_exception(exc) from None

    return wrapper


class RestMixin:

    @property
    def url(self):
        return appendslash(urljoin(self.server_url, self.path))

    @wrap_exception
    def _request(self, method, subpath=None, **kwargs):
        url = self.url
        if subpath is not None:
            url = urljoin(url, quote(subpath))
        url = appendslash(url)
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        if response.status_code != 204:
            return response.json()

    def _get(self, subpath=None, **kwargs):
        return self._request('get', subpath, **kwargs)

    def _post(self, subpath=None, **kwargs):
        return self._request('post', subpath, **kwargs)

    def _put(self, subpath=None, **kwargs):
        return self._request('put', subpath, **kwargs)

    def _patch(self, subpath=None, **kwargs):
        return self._request('patch', subpath, **kwargs)

    def _delete(self, subpath=None, **kwargs):
        return self._request('delete', subpath, **kwargs)


class CollectionCreateMixin:

    def create(self, *args, **kwargs):
        data = dict(*args, **kwargs)
        response_data = self._post(json=data)
        return self._resource(response_data)


class CollectionReadMixin:

    def get(self, identifier):
        data = self._get(identifier)
        return self.resource_class(self.server_url, data)

    def all(self):
        return self.filter()

    def filter(self, *args, **kwargs):
        params = dict(*args, **kwargs)
        return [
            self._resource(item)
            for item in self._get(params=params)
        ]


class CollectionShortcutsMixin:

    def get_or_create(self, identifier, defaults=None):
        try:
            return self.get(identifier)
        except exceptions.NotFoundError:
            pass

        if defaults is None:
            defaults = {}
        else:
            defaults = dict(defaults)

        lookup_field = self.resource_class.Meta.lookup_field
        if lookup_field:
            defaults[lookup_field] = identifier

        return self.create(defaults)

    def update_or_create(self, identifier, data=None):
        if data is None:
            data = {}
        else:
            data = dict(data)

        lookup_field = self.resource_class.Meta.lookup_field
        if lookup_field:
            data[lookup_field] = identifier

        try:
            obj = self.get(identifier)
        except exceptions.NotFoundError:
            obj = self.create(data)
        else:
            obj.data.update(data)
            obj.update()

        return obj


class Collection(
        CollectionCreateMixin,
        CollectionReadMixin,
        CollectionShortcutsMixin,
        RestMixin):

    def __init__(self, server_url, resource_class):
        self.server_url = server_url
        self.resource_class = resource_class

    @property
    def url(self):
        resource_path = self.resource_class.Meta.path
        return appendslash(urljoin(self.server_url, resource_path))

    def _resource(self, data):
        return self.resource_class(self.server_url, data)


class CollectionWrapper:

    def __init__(self, resource_class):
        self.resource_class = resource_class
        self.collection_class = getattr(resource_class, 'collection_class', Collection)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self.collection_class(instance.url, self.resource_class)


class ReadResourceMixin:

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def refresh(self, fields=None):
        data = self._get()

        if fields is not None:
            partial_data = {}
            for key in fields:
                try:
                    partial_data[key] = data[key]
                except KeyError:
                    pass
            data = partial_data

        self.data.update(data)


class WriteResourceMixin:

    def __setitem__(self, key, value):
        self.data[key] = value

    def update(self):
        self._put(json=self.data)

    def patch(self, fields):
        partial_data = {key: self[key] for key in fields}
        self._patch(json=partial_data)


class DeleteResourceMixin:

    def delete(self):
        self._delete()


class Resource(
        ReadResourceMixin,
        WriteResourceMixin,
        DeleteResourceMixin,
        RestMixin):

    def __init__(self, server_url, data):
        self.server_url = server_url
        self.data = data

    @classmethod
    def as_collection(cls):
        return CollectionWrapper(cls)

    @classmethod
    def url_for(cls, server_url, identifier):
        path = cls.Meta.path
        collection_url = urljoin(server_url, path)
        escaped_id = quote(identifier, safe='')
        return appendslash(urljoin(collection_url, escaped_id))

    @property
    def identifier(self):
        return self[self.Meta.lookup_field]

    @property
    def url(self):
        return type(self).url_for(self.server_url, self.identifier)

    def __repr__(self):
        return '<{}: {!r}>'.format(self.__class__.__name__, self.identifier)
