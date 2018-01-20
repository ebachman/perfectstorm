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

class PerfectStormException(Exception):

    pass


class ValidationError(PerfectStormException):

    def __init__(self, *args, field=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.field = field

    def __str__(self):
        s = super().__str__()
        if self.field is None:
            return s
        else:
            return '{}: {}'.format(self.field, s)


class APIException(PerfectStormException):

    pass


class APIRequestError(APIException):

    def __init__(self, *args, request=None, response=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.response = response
        if self.request is None and self.response is not None:
            self.request = self.response.request

    def __str__(self):
        if self.request is None:
            return ''
        req = '{} {}'.format(self.request.method, self.request.url)
        if self.response is None:
            return req
        resp = '{} {}'.format(self.response.status_code, self.response.reason)
        return '{} -> {}'.format(req, resp)


class APINotFoundError(APIRequestError):

    pass


class APIConflictError(APIRequestError):

    pass


class APIOSError(APIRequestError, OSError):

    def __str__(self):
        return '{}: {}'.format(APIRequestError.__str__(self), OSError.__str__(self))


class APIConnectionError(APIOSError, ConnectionError):

    pass


class APIIOError(APIOSError, IOError):

    pass


class ObjectNotFound(APIException):

    pass


class MultipleObjectsReturned(APIException):

    pass


class TriggerError(PerfectStormException):

    def __init__(self, *args, trigger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigger = trigger
