import abc
import logging
import time

try:
    import gevent
except ImportError:
    gevent = None


class BaseExecutor(metaclass=abc.ABCMeta):

    def __init__(
            self, restart=False, restart_interval=1, on_error='log'):
        self.restart = restart
        self.restart_interval = 1
        self.on_error_behavior = on_error

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
        if self.on_error_behavior == 'raise':
            raise exc
        elif self.on_error_behavior == 'log':
            logging.getLogger('stormlib.executors').exception(exc)
        else:
            raise RuntimeError(
                'unknown on_error behavior: {!r}'.format(
                    self.on_error_behavior))


class JobsExecutor(BaseExecutor):

    def run(self):
        for job in self.iter_jobs():
            try:
                self.run_job(job)
            except Exception as exc:
                self.on_job_error(job, exc)

    def before_run(self):
        pass

    @abc.abstractmethod
    def iter_jobs(self):
        raise NotImplementedError

    def run_job(self, job):
        job()

    def after_run(self):
        pass

    def on_job_error(self, job, exc):
        self.on_error(exc)


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
                self.on_job_error(job, exc)
            if not self.restart_jobs:
                break
            time.sleep(self.restart_jobs_interval)

    @abc.abstractmethod
    def wait_jobs(self, job):
        raise NotImplementedError

    @abc.abstractmethod
    def stop_jobs(self, job):
        raise NotImplementedError


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
