import random

import pytest


@pytest.fixture(scope='session', autouse=True)
def swarm_cluster():
    from stormlib import Agent, Resource

    swarm_agents = Agent.objects.filter(**{
        'type': 'swarm',
        'status': 'online',
        'options.autoLabeling': True,
        'options.procedureRunner': True,
    })

    if not swarm_agents:
        if not Agent.objects.filter(type='swarm', status='online'):
            pytest.skip('storm-swarm not running')
        else:
            pytest.skip(
                'no storm-swarm running with autoLabeling and '
                'procedureRunner enabled')

    swarm_agent_ids = [agent.id for agent in swarm_agents]
    swarm_clusters = Resource.objects.filter(
        type='swarm-cluster', owner={'$in': swarm_agent_ids})

    if not swarm_clusters:
        pytest.skip('no swarm clusters detected')

    return random.choice(swarm_clusters)


@pytest.fixture(scope='session')
def swarm_service(swarm_cluster):
    from ..samples import delete_on_exit
    from .samples import create_service, delete_service

    resource = create_service(swarm_cluster)

    with delete_on_exit(resource, delete_service):
        yield resource
