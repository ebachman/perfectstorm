import functools
import threading
import traceback


_TASKS = {}
_THREADS = {}
_LOCK = threading.RLock()


def register_task(name, factory_func):
    with _LOCK:
        if name in _TASKS:
            raise KeyError('a task named {!r} already exist'.format(name))
        _TASKS[name] = factory_func
    return functools.partial(run_task, factory_func)


def run_every(seconds):
    def callback(func):
        name = func.__name__
        factory_func = functools.partial(
            PeriodicJob, interval=seconds, function=func, name='task:' + name)
        wrapper = register_task(name, factory_func)
        return functools.update_wrapper(wrapper, func)

    return callback


def run_task(name):
    with _LOCK:
        try:
            thread = _THREADS[name]
        except KeyError:
            pass
        else:
            if thread.is_alive():
                return

        factory_func = _TASKS[name]
        thread = factory_func()
        thread.start()

        _THREADS[name] = thread


def run_tasks():
    with _LOCK:
        for name in _TASKS:
            run_task(name)


def stop_tasks():
    with _LOCK:
        for thread in _THREADS.values():
            thread.cancel()
        for thread in _THREADS.values():
            thread.join()
        _THREADS.clear()


class PeriodicJob(threading.Thread):

    def __init__(self, interval, function, args=None, kwargs=None, name=None):
        super().__init__()
        self.interval = interval
        self.function = function
        self.args = args if args is not None else ()
        self.kwargs = kwargs if kwargs is not None else {}
        self.name = name
        self.finished = threading.Event()
        self.daemon = True

    def cancel(self):
        self.finished.set()

    def run(self):
        while not self.finished.wait(self.interval):
            try:
                self.function(*self.args, **self.kwargs)
            except Exception as exc:
                traceback.print_exc()


@run_every(seconds=10)
def cleanup_stale_triggers():
    from teacup.apiserver.models import Trigger
    Trigger.objects.stale().update(status='pending')
