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
        self._obj = model_class.objects.get(self.id)
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


class EventMask(namedtuple(
        'BaseEventMask', 'event_type entity_type entity_id entity_names')):

    def __new__(
            cls, event_type=None, entity=None,
            entity_type=None, entity_id=None, entity_names=None):
        if entity is not None:
            if (entity_type is not None or
                    entity_id is not None or
                    entity_names is not None):
                raise TypeError(
                    'entity cannot be specified together with entity_type, '
                    'entity_id or entity_names')
            entity_type = type(entity).__name__.lower()
            entity_id = entity.id

        if entity_names is not None:
            entity_names = frozenset(entity_names)

        return super().__new__(
            cls, event_type, entity_type, entity_id, entity_names)

    def matches(self, event):
        return (
            (self.event_type is None or
                self.event_type == event.type) and
            (self.entity_type is None or
                self.entity_type == event.entity.type) and
            (self.entity_id is None or
                self.entity_id == event.entity.id) and
            (not self.entity_names or
                not self.entity_names & set(event.entity.names))
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

        it = (
            Event._from_json(json.loads(line))
            for line in response.iter_lines()
            if line
        )

        return EventsStream(response, it)


class EventsStream:

    def __init__(self, response, iterator):
        self._response = response
        self._iterator = iterator

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iterator)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def close(self):
        self._response.close()


class EventFilter:

    def __init__(self, masks=()):
        self.registered_events = set()
        for event_mask in masks:
            self.register(event_mask)

    def register(self, event_mask):
        self.registered_events.add(event_mask)

    def match(self, event):
        return tuple(
            event_mask for event_mask in self.registered_events
            if event_mask.matches(event)
        )

    def _filter(self, stream):
        for event in stream:
            masks = self.match(event)
            if masks:
                yield event, masks

    def __call__(self, stream):
        it = self._filter(stream)
        if isinstance(stream, EventsStream):
            return EventsStream(stream, it)
        else:
            return it


def latest(start=None, count=None, session=None):
    return EventReader(session=session).latest(start, count)


def stream(start=None, session=None):
    return EventReader(session=session).stream(start)
