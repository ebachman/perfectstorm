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
import urllib.parse

import requests


_lock = threading.RLock()
_global_session = None
_local_sessions = threading.local()

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8000


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


class UrlPath:

    def __new__(cls, url):
        if isinstance(url, UrlPath):
            url = str(url)
        if not isinstance(url, str):
            raise TypeError('Expected a string or UrlPath object, got {!r}'.format(url))
        return super().__new__(cls)

    def __init__(self, url):
        self._url = url.rstrip('/')

    def join(self, path, quote=False):
        if quote:
            path = urllib.parse.quote(path)
        else:
            path = path.strip('/')
        suburl = urllib.parse.urljoin(self._url + '/', path)
        return self.__class__(suburl)

    def __truediv__(self, other):
        if isinstance(other, UrlPath):
            other = str(other)
        if not isinstance(other, str):
            return NotImplemented
        return self.join(other)

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