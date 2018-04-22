import json
import random

import pytest

from ..stubs import random_name


@pytest.fixture(scope='session', autouse=True)
def skip_without_swarm(request, api_session):
    """Skip the execution of tests if storm-swarm is not running."""
    from stormlib import Agent, Resource

    swarm_agents = Agent.objects.filter(type='swarm', status='online')
    swarm_clusters = Resource.objects.filter(type='swarm-cluster')

    if not swarm_agents:
        pytest.skip('storm-swarm not running')
    if not swarm_clusters:
        pytest.skip('no swarm clusters detected')


@pytest.fixture(scope='session')
def swarm_cluster():
    from stormlib import Resource
    return random.choice(Resource.objects.filter(type='swarm-cluster'))


@pytest.fixture(scope='session')
def swarm_service(request, swarm_cluster):
    from stormlib import Resource, Job

    service_name = random_name()

    job = Job(
        type='swarm',
        target=swarm_cluster.id,
        content=json.dumps([
            'service create --name {} nginx:latest'.format(service_name)
        ]),
    )
    job.save()
    job.wait()

    yield Resource.objects.get(service_name)

    if request.config.getoption('--no-cleanup'):
        return

    job = Job(
        type='swarm',
        target=swarm_cluster.id,
        content=json.dumps([
            'service rm {}'.format(service_name)
        ]),
    )
    job.save()
    job.wait()
