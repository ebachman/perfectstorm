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
