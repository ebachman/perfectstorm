import abc

from ..api import Trigger, Procedure
from . import AgentExecutor, PollingExecutor


class TriggerExecutor(AgentExecutor, PollingExecutor):

    def get_pending_triggers(self):
        return Trigger.objects.filter(status='pending')

    def poll(self):
        pending_triggers = self.get_pending_triggers()
        if pending_triggers:
            self.trigger = pending_triggers[0]
            return True

    def run_inner(self):
        trigger = self.trigger
        with trigger.handle(self.agent):
            try:
                result = self.run_trigger(self.trigger)
            except Exception as exc:
                self.trigger_error(trigger, exc)
                raise
            else:
                self.trigger_done(trigger, result)

    @abc.abstractmethod
    def run_trigger(self, trigger):
        raise NotImplementedError

    def trigger_done(self, trigger, result):
        self.trigger.complete(result)

    def trigger_error(self, trigger, exc):
        self.trigger.fail(exc)


class ProcedureExecutor(TriggerExecutor):

    def run_trigger(self, trigger):
        self.procedure = self.get_procedure(trigger)
        self.run_procedure(self.procedure)

    def get_procedure(self, trigger):
        if trigger.procedure is None:
            return trigger

        procedure = Procedure.objects.get(trigger.procedure)

        # XXX procedure.options.update(trigger.options)
        # XXX procedure.params.update(trigger.params)

        return procedure

    @abc.abstractmethod
    def run_procedure(self, procedure):
        raise NotImplementedError
