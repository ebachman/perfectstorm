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

import threading
from urllib.parse import urljoin


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
        url = urljoin(self.instance.url + '/', 'heartbeat')
        self.instance._session.post(url)

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
