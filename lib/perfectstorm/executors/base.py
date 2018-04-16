import abc
import time


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
