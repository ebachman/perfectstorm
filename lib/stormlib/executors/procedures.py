import abc

from . import AgentExecutorMixin, PollingExecutor
from .. import Procedure, Job, events


class ProcedureRunner:

    def __init__(self, agent, job):
        self.agent = agent
        self.job = job

    def __call__(self):
        self.prepare()

        with self.job.handle(self.agent):
            try:
                result = self.run()
            except Exception as exc:
                self.fail(exc)
            else:
                self.complete(result)

    def prepare(self):
        job = self.job

        if job.procedure is None:
            return

        procedure = Procedure.objects.get(job.procedure)

        job.options = {**procedure.options, **job.options}
        job.params = {**procedure.params, **job.params}

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def fail(self, exc):
        self.job.fail(exc)

    def complete(self, exc):
        self.job.complete(exc)


class ProcedureExecutor(AgentExecutorMixin, PollingExecutor):

    def get_job_event_filter(self):
        return events.EventFilter([
            events.EventMask(event_type='created', entity_type='job'),
            events.EventMask(event_type='updated', entity_type='job'),
        ])

    def get_pending_jobs(self):
        return Job.objects.filter(status='pending')

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
