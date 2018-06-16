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
            cls, event_type=None, entity_type=None, entity_id=None,
            entity_names=None):
        if entity_names is not None:
            entity_names = frozenset(entity_names)
        return super().__new__(
            cls, event_type, entity_type, entity_id, entity_names)

    @classmethod
    def from_string(cls, s):
        """
        Construct an EventMask from a string in the following format:

            '<event_type>:<entity_type>:<entity_id>:<name1>,<name2>,...'

        Fields can be omitted and trailing colons are optional.

        Examples:

            EventMask.from_string(
                'created:resource:res-4ANqadEgfdRKo8OKG956VA:nginx.1')
            # is equivalent to:
            EventMask(event_type='created',
                `     entity_type='resource',
                      entity_id='res-4ANqadEgfdRKo8OKG956VA',
                      entity_names=['nginx.1'])

            EventMask.from_string('created:resource')
            # is equivalent to:
            EventMask.from_string('created:resource::')
            # is equivalent to:
            EventMask(event_type='created',
                `     entity_type='resource',
                      entity_id=None,
                      entity_names=None)

            EventMask.from_string('::res-4ANqadEgfdRKo8OKG956VA')
            # is equivalent to:
            EventMask.from_string('::res-4ANqadEgfdRKo8OKG956VA:')
            # is equivalent to:
            EventMask(event_type=None,
                `     entity_type=None,
                      entity_id='res-4ANqadEgfdRKo8OKG956VA',
                      entity_names=None)

            EventMask.from_string(':::a,b,c')
            # is equivalent to:
            EventMask(event_type=None,
                `     entity_type=None,
                      entity_id=None,
                      entity_names=['a', 'b', 'c'])
        """
        parts = s.split(':')

        if len(parts) > 4:
            raise ValueError(
                'expected at most 4 colon-separated fields, got {!r}'
                .format(s))

        args = (item if item else None for item in parts)
        return cls(*args)

    def matches(self, event):
        return (
            (self.event_type is None or
                self.event_type == event.type) and
            (self.entity_type is None or
                self.entity_type == event.entity.type) and
            (self.entity_id is None or
                self.entity_id == event.entity.id) and
            (not self.entity_names or
                self.entity_names & set(event.entity.names))
        )


class EventReader:

    @property
    def url(self):
        return current_session.api_root / 'v1/events'

    def latest(self, start=None, count=None):
        params = {}
        if start is not None:
            params['start'] = start
        if count is not None:
            params['count'] = count

        data = current_session.get(self.url, params=params)
        return [Event._from_json(item) for item in data]

    def stream(self, start=None):
        params = {'stream': 'true'}
        if start is not None:
            params['start'] = start

        response = current_session.get(
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
        self.masks = set()
        self.register_all(masks)

    def register(self, event_mask):
        if isinstance(event_mask, str):
            event_mask = EventMask.from_string(event_mask)
        self.masks.add(event_mask)

    def register_all(self, masks):
        for event_mask in masks:
            self.register(event_mask)

    def clear(self):
        self.masks.clear()

    def match(self, event):
        return tuple(
            event_mask for event_mask in self.masks
            if event_mask.matches(event)
        )

    def _filter(self, stream):
        for event in stream:
            masks = self.match(event)
            if masks:
                yield event

    def __call__(self, stream):
        it = self._filter(stream)
        if isinstance(stream, EventsStream):
            return EventsStream(stream, it)
        else:
            return it


def latest(filters=None, start=None, count=None):
    events = EventReader().latest(start, count)
    if filters is not None:
        event_filter = EventFilter(filters)
        events = event_filter(events)
    return events


def stream(filters=None, start=None):
    event_stream = EventReader().stream(start)
    if filters is not None:
        event_filter = EventFilter(filters)
        event_stream = event_filter(event_stream)
    return event_stream
