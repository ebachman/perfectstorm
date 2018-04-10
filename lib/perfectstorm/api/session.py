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

import logging
import threading
import urllib.parse

import requests
from requests.exceptions import RequestException

from .. import exceptions


log = logging.getLogger(__name__)

_lock = threading.RLock()
_global_session = None
_local_sessions = threading.local()

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8000


def _get_current_session():
    try:
        return _local_sessions.session_stack[-1]
    except (AttributeError, IndexError):
        pass

    session = _global_session
    if session is not None:
        return session

    raise RuntimeError('No active connections found. You must call connect() or use a Session object in a context manager')


def current_session():
    return CurrentSessionProxy()


def connect(host=None, port=None):
    global _global_session
    session = Session(host, port)
    with _lock:
        _global_session = session
    return session


class UrlPath:

    def __init__(self, url):
        if isinstance(url, UrlPath):
            url = str(url)
        if not isinstance(url, str):
            raise TypeError('Expected a string or UrlPath object, got {!r}'.format(type(url).__name__))
        self._url = url.rstrip('/')

    def params(self, *args, **kwargs):
        new_query_params = dict(*args, **kwargs)
        if not new_query_params:
            return self

        parsed_url = urllib.parse.urlparse(self._url)
        query_params = urllib.parse.parse_qsl(parsed_url.query)
        query_params.extend(new_query_params.items())
        query_string = urllib.parse.urlencode(query_params)

        parsed_url = parsed_url._replace(query=query_string)
        url = urllib.parse.urlunparse(parsed_url)

        return self.__class__(url)

    def __truediv__(self, other):
        if not isinstance(other, (str, UrlPath)):
            return NotImplemented

        left = self._url + '/'
        if isinstance(other, str):
            right = urllib.parse.quote(other)
        else:
            right = str(other)

        newurl = urllib.parse.urljoin(left, right)
        return self.__class__(newurl)

    def __str__(self):
        return self._url

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, str(self))


class Session:

    def __init__(self, host=None, port=None):
        if host is None:
            host = DEFAULT_HOST
        if port is None:
            port = DEFAULT_PORT
        self.api_root = UrlPath('http://%s:%d/' % (urllib.parse.quote(host), port))

    def _check_url(self, url):
        root = str(self.api_root) + '/'
        if not str(url).startswith(root):
            raise RuntimeError('URL has been mangled: %r' % url)

    def request(self, method, path, **kwargs):
        url = self.api_root / path
        self._check_url(url)

        try:
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise self.wrap_exception(exc)
        except exceptions.APIRequestError as exc:
            log.error('%s', exc)
            if log.isEnabledFor(logging.DEBUG) and exc.response is not None:
                log.debug('Response body: %s', exc.response.text)
            raise

        request = response.request
        log.info('%s %s -> %s %s', request.method, request.url, response.status_code, response.reason)

        if response.status_code != 204:
            return response.json()

    def wrap_exception(self, exc):
        root_cause = exc
        while root_cause.__context__ is not None:
            root_cause = root_cause.__context__

        exc_args = ()
        request = getattr(exc, 'request')
        response = getattr(exc, 'response')

        if isinstance(root_cause, OSError) and not isinstance(root_cause, RequestException):
            if isinstance(root_cause, ConnectionError):
                exc_type = exceptions.APIConnectionError
            elif isinstance(root_cause, IOError):
                exc_type = exceptions.APIIOError
            else:
                exc_type = exceptions.APIOSError
            exc_args = (root_cause.errno, root_cause.strerror)
        else:
            status_code = getattr(response, 'status_code', None)
            if status_code == 404:
                exc_type = exceptions.APINotFoundError
            elif status_code == 409:
                exc_type = exceptions.APIConflictError
            else:
                exc_type = exceptions.APIRequestError

        return exc_type(*exc_args, request=request, response=response)

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

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, str(self.api_root))


class CurrentSessionProxy:

    @property
    def real(self):
        return _get_current_session()

    def __getattr__(self, name):
        return getattr(self.real, name)

    def __setattr__(self, name, value):
        return setattr(self.real, name, value)

    def __repr__(self):
        try:
            api_root = str(self.real.api_root)
        except RuntimeError:
            api_root = 'not connected'
        return '<{}: {}>'.format(self.__class__.__name__, api_root)
