import abc
import multiprocessing
import time


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
