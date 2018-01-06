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

from ..entities import Trigger, Recipe
from . import AgentExecutor, PollingExecutor


class TriggerExecutor(AgentExecutor, PollingExecutor):

    @property
    @abc.abstractmethod
    def trigger_type(self):
        raise NotImplementedError

    def get_pending_triggers(self):
        return Trigger.objects.filter(
            type=self.trigger_type, status='pending')

    def poll(self):
        pending_triggers = self.get_pending_triggers()
        if pending_triggers:
            self.trigger = pending_triggers[0]
            return True

    def cycle(self):
        with self.trigger.handle(self.agent):
            try:
                result = self.handle_trigger()
            except Exception as exc:
                self.trigger_error(exc)
            else:
                self.trigger_done(result)

    @abc.abstractmethod
    def handle_trigger(self):
        raise NotImplementedError

    def trigger_done(self, result):
        self.trigger.complete(result)

    def trigger_error(self, exc):
        self.trigger.fail(exc)
        self.error(exc)


class RecipeExecutor(TriggerExecutor):

    trigger_type = 'recipe'

    def handle_trigger(self):
        recipe = self.get_recipe()
        self.run_recipe(recipe)

    def get_recipe(self):
        arguments = self.trigger.arguments

        recipe_name = arguments['recipe']
        recipe = Recipe.objects.get(name=recipe_name)

        if arguments.get('options'):
            recipe.options.update(arguments['options'])

        if arguments.get('params'):
            recipe.params.update(arguments['params'])

        return recipe

    @abc.abstractmethod
    def run_recipe(self):
        raise NotImplementedError
