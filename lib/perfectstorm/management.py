import abc

from . clients.monitor import GroupMembersMonitor


class Manager(metaclass=abc.ABCMeta):

    def __init__(self, api, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = api

    @property
    @abc.abstractmethod
    def name(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_monitors(self):
        raise NotImplementedError


class ServerManager(Manager):

    def __init__(self, backend, nodes_pool_group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend = backend
        self.nodes_pool_group = nodes_pool_group

    @abc.abstractmethod
    def update(self, force=False):
        raise NotImplementedError


class BackendManager(Manager):

    @abc.abstractmethod
    def update(self, server, force=False):
        raise NotImplementedError


class SingleServerManager(ServerManager):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.server = None

        self.recipe = self.create_recipe()
        self.server_group = self.create_server_group()
        self.node_group = self.create_node_group()

        self.server_group_monitor = GroupMembersMonitor(self.server_group)

    def get_monitors(self):
        monitors = [self.server_group_monitor]
        monitors.extend(self.backend.get_monitors())
        return monitors

    @property
    @abc.abstractmethod
    def recipe_data(self):
        raise NotImplementedError

    def create_recipe(self):
        return self.api.recipes.update_or_create(
            self.name, self.recipe_data)

    def create_server_group(self):
        name = '-'.join((
            self.nodes_pool_group.identifier,
            self.backend.name,
            self.name,
        ))
        return self.api.groups.update_or_create(name, {
            'query': {},
        })

    def create_node_group(self):
        name = '-'.join((
            self.nodes_pool_group.identifier,
            self.backend.name,
            self.name,
            'node',
        ))
        return self.api.groups.update_or_create(name, {
            'query': {},
        })

    def update(self, force=False):
        if force or self.server is None or self.server_group_monitor.has_changed():
            if force:
                self.server_group_monitor.refresh()
            self.ensure_server_running()
            self.backend.update(self, force=True)
        else:
            self.backend.update(self, force=force)

    def ensure_server_running(self):
        running_members = self.server_group.members(status='UP')

        if not running_members:
            server_id = self.deploy_server()
            self.server, = self.api.query(_id=server_id)
        else:
            assert len(running_members) == 1
            self.server, = running_members

    def deploy_server(self):
        running_nodes = self.node_group.members(status='UP')
        if running_nodes:
            assert len(running_nodes) == 1
            node, = running_nodes
        else:
            node = None

        trigger = self.api.triggers.run(
            'recipe',
            recipe=self.recipe.identifier,
            params=self.get_recipe_params(),
            targetNode=node['cloud_id'] if node is not None else None,
            targetAnyOf=self.nodes_pool_group.identifier,
            addTo=self.server_group.identifier)
        result = trigger['result']

        assert len(result['created']) == 1
        assert len(result['deleted']) == 0
        assert len(result['updated']) == 0

        server_id = result['created'][0]

        node = self.api.shortcuts.get_node_for(server_id)
        self.node_group.set_members([node['cloud_id']])

        print('Started new {} {} on {}'.format(self.name, server_id, node['name']))

        return server_id

    def get_recipe_params(self):
        return {}


class GroupBackendManager(BackendManager):

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.group_monitor = GroupMembersMonitor(self.group)

    @property
    def name(self):
        return self.group.identifier

    def get_monitors(self):
        return [self.group_monitor]

    def update(self, server, force=False):
        if force or self.group_monitor.has_changed():
            if force:
                self.group_monitor.refresh()
            self.update_members(server)

    @abc.abstractmethod
    def update_members(self, server):
        raise NotImplementedError
