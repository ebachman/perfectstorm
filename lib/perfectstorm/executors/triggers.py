import abc
import sys
import time
import traceback

from .. import exceptions
from . import PollingExecutor


class TriggerExecutor(PollingExecutor):

    trigger_handler = None

    def __init__(self, trigger_handler=None, **kwargs):
        if trigger_handler is not None:
            self.trigger_handler = trigger_handler
        if self.trigger_handler is None:
            raise ValueError('no trigger_handler specified')
        if self.trigger_handler.trigger_name is None:
            raise ValueError('trigger_handler has no trigger_name')
        super().__init__(**kwargs)

    @property
    def trigger_name(self):
        return self.trigger_handler.trigger_name

    def poll(self):
        self.pending_triggers = self.list_pending_triggers()
        return bool(self.pending_triggers)

    def list_pending_triggers(self):
        return self.api.triggers.filter(name=self.trigger_name, status='pending')

    def run(self):
        self.handle_pending_triggers()

    def handle_pending_triggers(self):
        for trigger in self.pending_triggers:
            self.handle_trigger(trigger)

    def handle_trigger(self, trigger):
        handler = self.trigger_handler(self, trigger)

        try:
            handler.handle_trigger()
        except Exception as exc:
            handler.handle_trigger_exception(exc)


class TriggerHandler(metaclass=abc.ABCMeta):

    trigger_name = None

    def __init__(self, executor, trigger):
        self.executor = executor
        self.api = executor.api
        self.trigger = trigger

    def handle_trigger(self):
        try:
            handler = self.trigger.handle()
        except exceptions.NotFoundError as exc:
            if exc.request.url == self.trigger.url:
                return
            raise

        print('Running trigger', self.trigger.identifier)

        handler.start_heartbeat()

        try:
            result = self.run_trigger()
            self.handle_trigger_done(result)
        finally:
            handler.cancel_heartbeat()

    @abc.abstractmethod
    def run_trigger(self):
        raise NotImplementedError

    def handle_trigger_done(self, result=None):
        self.trigger.complete(result)

    def handle_trigger_exception(self, exc):
        print('Exception while handling trigger', self.trigger.identifier, file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        self.trigger.fail(exc)


class RecipeTriggerHandler(TriggerHandler):

    trigger_name = 'recipe'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resources_created = []
        self.resources_updated = []
        self.resources_deleted = []

    def run_trigger(self):
        self.retrieve_recipe()

        if self.target_node is not None:
            nodes = [self.target_node]
        elif self.target_any_of is not None:
            nodes = [self.choose_node(self.target_any_of)]
        elif self.target_all_in is not None:
            nodes = self.filter_nodes(self.target_all_in)
        else:
            raise ValueError('No targets specified')

        for node in nodes:
            self.run_recipe(node)

        print('Created {} new resources, updated {} resources, deleted {} resources from recipe {!r}'.format(
            len(self.resources_created), len(self.resources_updated), len(self.resources_deleted), self.recipe.identifier))

        return {
            'created': self.resources_created,
            'updated': self.resources_updated,
            'deleted': self.resources_deleted,
        }

    def retrieve_recipe(self):
        arguments = self.trigger['arguments']

        # Find the recipe.
        recipe_name = arguments['recipe']
        self.recipe = self.api.recipes.get(recipe_name)

        # Find the options.
        self.recipe_options = {}
        if self.recipe.get('options'):
            self.recipe_options.update(self.recipe.get('options'))
        if arguments.get('options'):
            self.recipe_options.update(arguments.get('options'))

        # Find the params.
        self.recipe_params = {}
        if self.recipe.get('params'):
            self.recipe_params.update(self.recipe.get('params'))
        if arguments.get('params'):
            self.recipe_params.update(arguments.get('params'))

        # Find the target.
        self.target_node = None
        self.target_any_of = None
        self.target_all_in = None

        if arguments.get('targetNode'):
            matching_nodes = self.api.query(_id=arguments.get('targetNode'))
            assert len(matching_nodes) == 1

            self.target_node = matching_nodes[0]
        else:
            for databag in (arguments, self.recipe):
                for keyword, attribute in (('targetAnyOf', 'target_any_of'),
                                           ('targetAllIn', 'target_all_in')):
                    value = databag.get(keyword)
                    if value:
                        group = self.api.groups.get(value)
                        setattr(self, attribute, group)

        if self.target_node is None and self.target_any_of is None and self.target_all_in is None:
            raise ValueError("No targets specified. Use one of 'targetNode', 'targetAnyOf' or 'targetAllIn'")

        # Find the "add to".
        add_to_name = arguments.get('addTo') or self.recipe.get('addTo')

        if add_to_name:
             self.add_to = self.api.groups.get(add_to_name)
        else:
            self.add_to = None

    def filter_nodes(self, group):
        return group.members()

    @abc.abstractmethod
    def choose_node(self, group):
        raise NotImplementedError

    @abc.abstractmethod
    def run_recipe(self):
        raise NotImplementedError

    def create_resource(self, resource_id):
        self.wait_resource(resource_id)
        if self.add_to is not None:
            self.add_to.add_members([resource_id])

        if resource_id not in self.resources_created:
            self.resources_created.append(resource_id)

    def update_resource(self, resource_id):
        if self.add_to is not None:
            self.add_to.add_members([resource_id])

        if resource_id not in self.resources_updated:
            self.resources_updated.append(resource_id)

    def delete_resource(self, resource_id):
        if resource_id not in self.resources_deleted:
            self.resources_deleted.append(resource_id)

    def wait_resource(self, resource_id):
        # HACK: wait for the new resources to be discovered before adding them to groups.
        while not self.api.query(_id=resource_id):
            self.executor.sleep()
