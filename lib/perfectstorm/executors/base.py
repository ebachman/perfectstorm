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

import abc
import time

from ..entities import Agent


class BaseExecutor(metaclass=abc.ABCMeta):

    def before_run(self):
        pass

    def run(self):
        self.before_run()

        try:
            self.run_inner()
        except Exception as exc:
            self.run_error(exc)
        finally:
            self.after_run()

    @abc.abstractmethod
    def run_inner(self):
        pass

    def after_run(self):
        pass

    def run_error(self, exc):
        self.error(exc)

    def error(self, exc):
        raise exc


class AgentExecutor(BaseExecutor):

    @property
    @abc.abstractmethod
    def agent_name(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = Agent(name=self.agent_name)

    def before_run(self):
        super().before_run()
        self.agent.save()
        self.agent.heartbeat.start()

    def after_run(self):
        super().after_run()
        self.agent.heartbeat.stop()
        self.agent.delete()


class LoopExecutor(BaseExecutor):

    def run_inner(self):
        while True:
            try:
                self.wait()
            except Exception as exc:
                self.wait_error(exc)
            try:
                self.cycle()
            except Exception as exc:
                self.cycle_error(exc)

    @abc.abstractmethod
    def wait(self):
        raise NotImplementedError

    def wait_error(self, exc):
        self.error(exc)

    @abc.abstractmethod
    def cycle(self):
        raise NotImplementedError

    def cycle_error(self, exc):
        self.error(exc)


class PollingExecutor(LoopExecutor):

    poll_interval = 1

    def wait(self):
        while not self.poll():
            self.sleep()

    def sleep(self):
        time.sleep(self.poll_interval)

    @abc.abstractmethod
    def poll(self):
        raise NotImplementedError

    def wait_error(self, exc):
        super().wait_error(exc)
        self.sleep()
