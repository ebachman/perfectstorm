import random

import pytest


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
    from .samples import create_service, delete_service

    resource = create_service(swarm_cluster)
    yield resource

    if request.config.getoption('--no-cleanup'):
        return

    delete_service(resource)
