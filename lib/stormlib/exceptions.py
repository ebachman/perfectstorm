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
