import abc

from .. import Trigger, Procedure
from . import AgentExecutorMixin, PollingExecutor


class ProcedureRunner:

    def __init__(self, agent, trigger):
        self.agent = agent
        self.trigger = trigger

    def __call__(self):
        self.prepare()

        with self.trigger.handle(self.agent):
            try:
                result = self.run()
            except Exception as exc:
                self.fail(exc)
            else:
                self.complete(result)

    def prepare(self):
        trigger = self.trigger

        if trigger.procedure is None:
            return

        procedure = Procedure.objects.get(trigger.procedure)

        trigger.options = {**procedure.options, **trigger.options}
        trigger.params = {**procedure.params, **trigger.params}

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def fail(self, exc):
        self.trigger.fail(exc)

    def complete(self, exc):
        self.trigger.complete(exc)


class ProcedureExecutor(AgentExecutorMixin, PollingExecutor):

    def get_pending_triggers(self):
        return Trigger.objects.filter(status='pending')

    def poll_jobs(self):
        return [
            self.procedure_runner(self.agent, trigger)
            for trigger in self.get_pending_triggers()
        ]

    @abc.abstractmethod
    def get_procedure_runner(self, agent, trigger):
        raise NotImplementedError
