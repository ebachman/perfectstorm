class PerfectStormException(Exception):

    pass


class PerfectStormHttpError(PerfectStormException):

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.response = kwargs.pop('response', None)
        super().__init__(*args, **kwargs)


class BadRequestError(PerfectStormHttpError):

    pass


class NotFoundError(PerfectStormHttpError):

    pass


class TriggerError(PerfectStormException):

    def __init__(self, *args, **kwargs):
        self.trigger = kwargs.pop('trigger', None)
        super().__init__(*args, **kwargs)
