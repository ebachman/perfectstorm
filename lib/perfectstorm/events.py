import json
from collections import namedtuple

from .api.session import current_session


Entity = namedtuple('Entity', 'type id names')
Event = namedtuple('Event', 'index type entity')


def _json2event(data):
    return Event(
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
        return [_json2event(item) for item in data]

    def stream(self, start=None):
        params = {'stream': 'true'}
        if start is not None:
            params['start'] = start

        response = self._session.get(
            self.url, params=params,
            stream=True, decode_json=False)

        for line in response.iter_lines():
            if line:
                yield _json2event(json.loads(line))


def latest(start=None, count=None, session=None):
    return EventReader(session=session).latest(start, count)


def stream(start=None, session=None):
    return EventReader(session=session).stream(start)
