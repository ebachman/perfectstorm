import random

from perfectstorm import Agent, Resource

from .stubs import random_name


def create_agent():
    agent = Agent(type='test')
    agent.save()
    return agent


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

def make_resource(**kwargs):
    resource = Resource(
        type=random.choice(RESOURCE_TYPES),
        names=[random_name() for i in range(random.randrange(6))],
        image=random.choice(RESOURCE_IMAGES),
        **kwargs,
    )

    resource.save()

    return resource


def create_random_resources(
        count=64, min_running_percent=0.6, min_healthy_percent=0.8):
    agent = create_agent()

    resources = []

    running_count = count * min_running_percent
    healthy_count = count * min_healthy_percent

    for i in range(count):
        if running_count:
            status = 'running'
            running_count -= 1
        else:
            status = random.choice(RESOURCE_STATUSES)

        if healthy_count:
            health = 'healthy'
            healthy_count -= 1
        else:
            health = random.choice(RESOURCE_HEALTHS)

        res = make_resource(owner=agent.id, status=status, health=health)
        resources.append(res)

    return resources
