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
import multiprocessing
import time

from ..entities import Agent


class Executor(metaclass=abc.ABCMeta):

    def run(self):
        self.before_run()
        try:
            self.run_inner()
        finally:
            self.after_run()

    def before_run(self):
        pass

    @abc.abstractmethod
    def run_inner(self):
        raise NotImplementedError

    def after_run(self):
        pass


class PollingExecutor(Executor):

    poll_interval = 1

    def run(self):
        self.before_run()
        try:
            while True:
                self.wait()
                self.run_inner()
        finally:
            self.after_run()

    def wait(self):
        while not self.poll():
            time.sleep(self.poll_interval)

    @abc.abstractmethod
    def poll(self):
        raise NotImplementedError


class AgentExecutor(Executor):

    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent


class ExecutorRunner:

    def __init__(self, executors):
        self.executors = list(executors)

    @abc.abstractmethod
    def dispatch(self, executor):
        raise NotImplementedError

    @abc.abstractmethod
    def wait(self):
        raise NotImplementedError

    @abc.abstractmethod
    def terminate(self):
        raise NotImplementedError


class ProcessExecutorRunner(ExecutorRunner):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processes = [[executor, None] for executor in self.executors]

    def _run(self, executor):
        try:
            executor.run()
        except KeyboardInterrupt:
            pass

    def dispatch(self):
        for pair in self._processes:
            executor, proc = pair
            if proc is None:
                proc = multiprocessing.Process(
                    target=self._run, args=(executor,))
                pair[1] = proc
                proc.start()

    def wait(self):
        for executor, proc in self._processes:
            if proc is not None:
                proc.join()

    def terminate(self):
        for executor, proc in self._processes:
            if proc is not None:
                proc.terminate()


class RestartingProcessExecutorRunner(ProcessExecutorRunner):

    def __init__(self, executors, restart_interval=1, **kwargs):
        super().__init__(executors, **kwargs)
        self.restart_interval = restart_interval

    def wait(self):
        try:
            while True:
                for pair in self._processes:
                    executor, proc = pair
                    if proc is not None and not proc.is_alive():
                        pair[1] = None

                self.dispatch()
                time.sleep(self.restart_interval)
        finally:
            self.terminate()
