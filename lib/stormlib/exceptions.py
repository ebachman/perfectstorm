import pprint


class StormException(Exception):
    """Base class for all exceptions raised by stormlib."""


class StormValidationError(StormException):
    """Exception raised when validating a model fails."""

    def __init__(self, *args, field=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.field = field

    def __str__(self):
        s = super().__str__()
        if self.field is None:
            return s
        else:
            return '{}: {}'.format(self.field, s)


class StormAPIError(StormException):
    """
    Base class for exceptions raised when an error occurs while communicating
    to the Storm API Server.
    """

    def __init__(
            self, *args, request=None, response=None,
            status_code=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request = request
        self.response = response
        self.status_code = status_code

        if self.response is not None:
            if self.status_code is None:
                self.status_code = getattr(self.response, 'status_code', None)
            if self.request is None:
                self.request = getattr(self.response, 'request', None)

    def __str__(self):
        parts = [
            self.status_code,
            getattr(self.request, 'method', None),
            getattr(self.request, 'url', None),
        ]
        return ' '.join(str(item) for item in parts if item)


class StormBadRequestError(StormAPIError):
    """Exception raised when the API returns a '400 Bad Request' response."""

    def details(self):
        try:
            return self._details
        except AttributeError:
            pass

        try:
            self._details = self.response.json()
        except Exception:
            self._details = None

        return self._details

    def __str__(self):
        s = super().__str__()
        details = self.details()
        if details is None:
            return s
        else:
            return '{}: {!r}'.format(s, details)


class StormNotFoundError(StormAPIError):
    """Exception raised when the API returns a '404 Not Found' response."""


class StormConflictError(StormAPIError):
    """Exception raised when the API returns a '409 Conflict' response."""


class StormOSError(StormAPIError, OSError):
    """
    Exception raised when an OSError occurs while attempting to send a request
    or receive a response.
    """

    def __str__(self):
        return '{}: {}'.format(
            StormAPIError.__str__(self), OSError.__str__(self))


class StormConnectionError(StormOSError, ConnectionError):
    """
    Exception raised when ConnectionError occurs while attempting to send a
    request or receive a response.
    """


class StormObjectNotFound(StormException):
    """
    Exception raised when a Model object cannot be retrieved because the Storm
    API Server is returning a '404 Not Found' error.
    """


class StormMultipleObjectsReturned(StormException):
    """
    Exception raised when a single Model object is expected, but the Storm API
    Server returned more than one.
    """


class StormJobError(StormException):
    """Exception raised when the execution of a job fails."""

    def __init__(self, *args, job=None, details=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        if details is None:
            details = getattr(self.job, 'result', None)
        self.details = details

    def __str__(self):
        s = super().__str__()
        if self.details is not None:
            str_details = pprint.pformat(self.details)
            s = '\n'.join((s, str_details))
        return s
