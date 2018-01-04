# Copyright (c) 2017, Composure.ai
# Copyright (c) 2018, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

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
def cleanup_stale_agents():
    from teacup.apiserver.models import Agent
    Agent.objects.stale().delete()


@run_every(seconds=10)
def cleanup_stale_triggers():
    from teacup.apiserver.models import Trigger
    Trigger.objects.stale().update(status='pending')
