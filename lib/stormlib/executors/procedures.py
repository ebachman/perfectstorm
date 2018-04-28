import abc
import logging

from . import AgentExecutorMixin, PollingExecutor
from .. import Job, events

log = logging.getLogger(__name__)


class ProcedureRunner:

    def __init__(self, agent, job):
        self.agent = agent
        self.job = job

    def __call__(self):
        with self.job.handle(self.agent.id):
            try:
                result = self.run()
            except Exception as exc:
                if not self.job.is_complete():
                    self.exception(exc)
            else:
                if not self.job.is_complete():
                    self.complete(result)

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def complete(self, result):
        self.job.complete(result)

    def fail(self, result):
        self.job.fail(result)

    def exception(self, exc):
        self.job.exception(exc)
        log.exception(exc)


class ProcedureExecutor(AgentExecutorMixin, PollingExecutor):

    @property
    @abc.abstractmethod
    def procedure_type(self):
        raise NotImplementedError

    def get_job_event_filter(self):
        return events.EventFilter([
            events.EventMask(event_type='created', entity_type='job'),
            events.EventMask(event_type='updated', entity_type='job'),
        ])

    def get_pending_jobs(self):
        return Job.objects.filter(
            type=self.procedure_type,
            status='pending',
        )

    def poll_jobs(self):
        event_filter = self.get_job_event_filter()

        with event_filter(events.stream()) as stream:
            while True:
                pending_jobs = self.get_pending_jobs()
                if pending_jobs:
                    break
                next(stream)

        return [
            self.get_procedure_runner(self.agent, job)
            for job in pending_jobs
        ]

    @abc.abstractmethod
    def get_procedure_runner(self, agent, job):
        raise NotImplementedError
