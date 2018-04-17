import json
from collections import namedtuple

from . import models
from .exceptions import StormObjectNotFound
from .session import current_session


class Entity(namedtuple('BaseEntity', 'type id names')):

    def retrieve(self):
        """Return the Model object referenced by this Entity."""
        try:
            return self._obj
        except AttributeError:
            # Object has not been fetched yet
            pass

        model_name = self.type.capitalize()
        if model_name not in models.__all__:
            raise StormObjectNotFound(self.id)

        model_class = getattr(models, model_name)
        self._obj = model_class.objects.retrieve(self.id)
        return self._obj


class Event(namedtuple('BaseEvent', 'index type entity')):

    @classmethod
    def _from_json(cls, data):
        return cls(
            index=data['id'],
            type=data['event_type'],
            entity=Entity(
                type=data['entity_type'],
                id=data['entity_id'],
                names=data['entity_names'],
            ),
        )


class EventReader:

    def __init__(self, session=None):
        if session is None:
            session = current_session()
        self._session = session

    @property
    def url(self):
        return self._session.api_root / 'v1/events'

    def latest(self, start=None, count=None):
        params = {}
        if start is not None:
            params['start'] = start
        if count is not None:
            params['count'] = count

        data = self._session.get(self.url, params=params)
        return [Event._from_json(item) for item in data]

    def stream(self, start=None):
        params = {'stream': 'true'}
        if start is not None:
            params['start'] = start

        response = self._session.get(
            self.url, params=params,
            stream=True, decode_json=False)

        for line in response.iter_lines():
            if line:
                yield Event._from_json(json.loads(line))


def latest(start=None, count=None, session=None):
    return EventReader(session=session).latest(start, count)


def stream(start=None, session=None):
    return EventReader(session=session).stream(start)
