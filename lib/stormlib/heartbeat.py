import threading

from .session import current_session


HEARTBEAT_DURATION = 60
DEFAULT_INTERVAL = HEARTBEAT_DURATION // 2


class _PeriodicTask(threading.Thread):

    def __init__(self, func, interval):
        super().__init__()
        self.func = func
        self.interval = interval
        self._stop_event = threading.Event()

    def run(self):
        func = self.func
        interval = self.interval
        event = self._stop_event

        while not event.wait(interval):
            func()

    def stop(self):
        self._stop_event.set()
        self.join()


class HeartbeatContextManager:

    def __init__(self, heartbeat):
        self.heartbeat = heartbeat

    def __enter__(self):
        self.heartbeat.start()
        return self.heartbeat.instance

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.heartbeat.stop()


class Heartbeat:

    def __init__(self, instance):
        self.instance = instance
        self._thread = None

    def _post_heartbeat(self):
        url = self.instance.url / 'heartbeat'
        current_session.post(url)

    def start(self, interval=None):
        if self._thread is None:
            if interval is None:
                interval = DEFAULT_INTERVAL
            self._thread = _PeriodicTask(self._post_heartbeat, interval)
        self._thread.start()

    def stop(self):
        if self._thread is not None:
            self._thread.stop()
            self._thread = None

    def __call__(self):
        self._post_heartbeat()
        return HeartbeatContextManager(self)
