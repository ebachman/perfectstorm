import collections
import contextlib
import threading
import time

import pytest

from stormlib import events
from stormlib.events import Event, Entity

from . import samples
from .stubs import ANY


def assert_event_in(expected_event, events_queue, wait=False):
    if isinstance(events_queue, list):
        events_queue = collections.deque(events_queue)

    if wait:
        # Wait for the event to appear for at least 5 seconds
        timeout = time.time() + 5

        # Check for the event in the queue, sleeping if necessary
        while time.time() < timeout:
            if not events_queue:
                time.sleep(.2)
                continue

            ev = events_queue.popleft()
            if ev == expected_event:
                return
    else:
        # Consume all the events until the expected event is found
        # (or the queue is empty)
        while events_queue:
            ev = events_queue.popleft()
            if ev == expected_event:
                return

    pytest.fail('{!r} not found'.format(expected_event))


def test_latest(agent):
    # Create a resource
    res = samples.create_resource(owner=agent.id)

    # Update it
    res.image = 'scrambled_egg'
    res.save()

    # Delete it
    res.delete()

    latest_events = collections.deque(events.latest())
    entity = Entity('resource', res.id, res.names)

    assert_event_in(Event(ANY, 'created', entity), latest_events)
    assert_event_in(Event(ANY, 'updated', entity), latest_events)
    assert_event_in(Event(ANY, 'deleted', entity), latest_events)


def test_latest_pagination(random_resources):
    # Retrieve a set of events
    latest_events = events.latest()

    # Retrieve the same set of events, this time using multiple calls
    # to latest() using different values for 'start' and 'count'
    start = latest_events[0].index
    stop = latest_events[-1].index + 1
    step = count = 3

    for i in range(start, stop, step):
        if i + step >= stop:
            # This is the last iteration. Make sure that we don't retrieve
            # more events than needed
            count = stop - i

        # Retrieve a small slice of events
        events_slice = events.latest(start=i, count=count)
        slice_size = len(events_slice)
        assert slice_size == count

        # Check that the events returned are exactly the same that were
        # returned by the first call to latest()
        assert latest_events[:slice_size] == events_slice

        # Delete the events that we already checked
        del latest_events[:slice_size]

    # Make sure we checked everything
    assert not latest_events


@contextlib.contextmanager
def collect_realtime_events(*args, **kwargs):
    events_iterator = events.stream(*args, **kwargs)
    events_queue = collections.deque()

    def feed():
        while not stop.is_set():
            ev = next(events_iterator)
            events_queue.append(ev)

    stop = threading.Event()
    thread = threading.Thread(target=feed, daemon=True)
    thread.start()

    try:
        yield events_queue
    finally:
        stop.set()


def test_stream(agent):
    with collect_realtime_events() as events:
        res = samples.create_resource(owner=agent.id)
        entity = Entity('resource', res.id, res.names)
        assert_event_in(Event(ANY, 'created', entity), events, wait=True)

        res.image = 'scrambled_egg'
        res.save()
        assert_event_in(Event(ANY, 'updated', entity), events, wait=True)

        res.delete()
        assert_event_in(Event(ANY, 'deleted', entity), events, wait=True)


def test_stream_start(agent):
    res = samples.create_resource(owner=agent.id)
    entity = Entity('resource', res.id, res.names)
    event = Event(ANY, 'created', entity)

    latest_events = events.latest()
    assert_event_in(event, latest_events)

    event_index = latest_events.index(event)
    start = latest_events[event_index].index

    with collect_realtime_events(start=start) as realtime_events:
        assert_event_in(event, realtime_events, wait=True)
