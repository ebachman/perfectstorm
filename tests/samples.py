import random

from stormlib import Agent, Resource, Group, Procedure
from stormlib.exceptions import StormObjectNotFound

from . import conftest
from .stubs import random_name


RESOURCE_TYPES = [
    'alpha',
    'beta',
    'gamma',
    'delta',
]

RESOURCE_IMAGES = [
    None,
    'library/mongo:latest',
    'library/nginx:1',
    'library/nginx:1.12',
    'library/nginx:1.12.2',
    'library/nginx:1.13',
    'library/nginx:1.13.12',
    'library/nginx:latest',
    'library/nginx:mainline',
    'pumpio/pump.io:alpha',
    'pumpio/pump.io:beta',
    'wikimedia/mediawiki:1.30.0-wmf3',
    'wikimedia/mediawiki:1.30.0-wmf3-1',
    'wikimedia/mediawiki:1.30.0-wmf3-2',
    'wikimedia/mediawiki:1.30.0-wmf3-3',
    'wikimedia/mediawiki:1.30.0-wmf4',
    'wikimedia/mediawiki:latest',
]

RESOURCE_STATUSES = [
    'unknown',
    'creating',
    'created',
    'starting',
    'running',
    'updating',
    'updated',
    'stopping',
    'stopped',
    'removing',
    'error',
]

RESOURCE_HEALTHS = [
    'unknown',
    'healthy',
    'unhealthy',
]


class delete_on_exit:

    def __init__(self, obj, deletefunc=None):
        self.obj = obj
        self.deletefunc = deletefunc

    def __enter__(self):
        return self.obj

    def __exit__(self, exc_type, exc_value, exc_tb):
        if not conftest.CLEANUP_ENABLED:
            return

        try:
            if self.deletefunc is not None:
                self.deletefunc(self.obj)
                return
            if hasattr(self.obj, 'delete'):
                self.obj.delete()
                return
        except StormObjectNotFound:
            return

        if hasattr(self.obj, '__iter__'):
            for item in self.obj:
                try:
                    item.delete()
                except StormObjectNotFound:
                    pass
            return

        raise RuntimeError('object has no delete() method')


def create_agent():
    agent = Agent(type='test')
    agent.save()
    return agent


def create_resource(**kwargs):
    resource = Resource(
        type=random.choice(RESOURCE_TYPES),
        names=[random_name() for i in range(random.randrange(6))],
        image=random.choice(RESOURCE_IMAGES),
        **kwargs,
    )

    resource.save()

    return resource


def create_random_resources(
        count=64, min_running_percent=0.6, min_healthy_percent=0.8,
        owner=None):
    if owner is None:
        owner = create_agent().id

    resources = []

    running_count = count * min_running_percent
    healthy_count = count * min_healthy_percent

    for i in range(count):
        if running_count > 0:
            status = 'running'
            running_count -= 1
        else:
            status = random.choice(RESOURCE_STATUSES)

        if healthy_count > 0:
            health = 'healthy'
            healthy_count -= 1
        else:
            health = random.choice(RESOURCE_HEALTHS)

        res = create_resource(owner=owner, status=status, health=health)
        resources.append(res)

    return resources


def create_group(query=None, include=None, exclude=None):
    group = Group(
        name=random_name(),
        query=query,
        include=include,
        exclude=exclude,
    )
    group.save()
    return group


def create_procedure(content=None, options=None, params=None):
    if content is None:
        content = '{{ x }} + {{ y }} = {{ x + y }}'
    if options is None:
        options = {'i': 1, 'j': 2, 'k': 3}
    if params is None:
        params = {'x': 1, 'y': 2, 'z': 3}

    procedure = Procedure(
        type='test',
        name=random_name(),
        content=content,
        options=options,
        params=params,
    )

    procedure.save()

    return procedure
