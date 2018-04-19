import abc
import time
import traceback

try:
    import gevent
except ImportError:
    gevent = None


class BaseExecutor(metaclass=abc.ABCMeta):

    def __init__(self, restart=False, restart_interval=1):
        self.restart = restart
        self.restart_interval = 1

    def __call__(self):
        while True:
            try:
                self.before_run()
                try:
                    self.run()
                finally:
                    self.after_run()
            except Exception as exc:
                self.on_error(exc)
                if not self.restart:
                    raise
            if not self.restart:
                break
            time.sleep(self.restart_interval)

    def before_run(self):
        pass

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def after_run(self):
        pass

    def on_error(self, exc):
        traceback.print_exception(type(exc), exc, exc.__traceback__)


class JobsExecutor(BaseExecutor):

    def run(self):
        for job in self.iter_jobs():
            self.run_job(job)

    def before_run(self):
        pass

    @abc.abstractmethod
    def iter_jobs(self):
        raise NotImplementedError

    def run_job(self, job):
        job()

    def after_run(self):
        pass


class PipelineExecutor(JobsExecutor):

    def __init__(self, jobs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._jobs = jobs

    def iter_jobs(self):
        return iter(self._jobs)


class PollingExecutor(JobsExecutor):

    def __init__(self, poll_interval=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_interval = poll_interval

    def iter_jobs(self):
        while True:
            yield from self.poll_jobs()
            time.sleep(self.poll_interval)

    @abc.abstractmethod
    def poll_jobs(self):
        raise NotImplementedError


class AsyncJobsExecutor(JobsExecutor):

    def __init__(
            self, restart_jobs=False, restart_jobs_interval=1,
            *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.restart_jobs = restart_jobs
        self.restart_jobs_interval = restart_jobs_interval

    def run(self):
        try:
            super().run()
            self.wait_jobs()
        except KeyboardInterrupt:
            self.stop_jobs()

    def run_job(self, job):
        self.spawn_job(job)

    @abc.abstractmethod
    def spawn_job(self, job):
        raise NotImplementedError

    def run_job_inner(self, job):
        while True:
            try:
                job()
            except Exception as exc:
                self.on_job_error(exc)
            if not self.restart_jobs:
                break
            time.sleep(self.restart_jobs_interval)

    @abc.abstractmethod
    def wait_jobs(self, job):
        raise NotImplementedError

    @abc.abstractmethod
    def stop_jobs(self, job):
        raise NotImplementedError

    def on_job_error(self, exc):
        self.on_error(exc)


class AsyncPipelineExecutor(AsyncJobsExecutor, PipelineExecutor):

    pass


class AsyncPollingExecutor(AsyncJobsExecutor, PollingExecutor):

    pass


if gevent:
    class GeventJobsExecutor(AsyncJobsExecutor):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._greenlets = set()

        def spawn_job(self, job):
            greenlet = gevent.spawn(self.run_job_inner, job)
            self._greenlets.add(greenlet)

        def run_job_inner(self, job):
            try:
                super().run_job_inner(job)
            finally:
                greenlet = gevent.getcurrent()
                self._greenlets.discard(greenlet)

        def wait_jobs(self):
            while self._greenlets:
                gevent.wait(self._greenlets)
                self._cleanup_greenlets()

        def stop_jobs(self):
            while self._greenlets:
                gevent.killall(self._greenlets)
                self._cleanup_greenlets()

        def _cleanup_greenlets(self):
            dead_greenlets = {
                greenlet for greenlet in self._greenlets if greenlet.dead}
            self._greenlets -= dead_greenlets

    class GeventPipelineExecutor(GeventJobsExecutor, AsyncPipelineExecutor):

        pass

    class GeventPollingExecutor(GeventJobsExecutor, AsyncPollingExecutor):

        pass


class AgentExecutorMixin:

    def __init__(self, agent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent
