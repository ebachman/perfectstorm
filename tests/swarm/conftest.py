import random

import pytest


def pick_cluster(agent_types):
    from stormlib import Agent, Resource

    # Get all the swarm clusters from the API Server
    all_clusters = {
        cluster.snapshot['Swarm']['Cluster']['ID']: cluster
        for cluster in Resource.objects.filter(type='swarm-cluster')}
    cluster_ids = set(all_clusters)

    # For each agent type, get the clusters managed by those agents
    for agent_type in agent_types:
        agents = Agent.objects.filter(type=agent_type, status='online')
        if not agents:
            pytest.skip('storm-{} not running'.format(agent_type))
        managed_cluster_ids = {agent.options['clusterId'] for agent in agents}
        # Keep only the clusters that are managed by the agents that
        # are required
        cluster_ids &= managed_cluster_ids

    if not cluster_ids:
        pytest.skip(
            'no swarm clusters managed by {}'.format(', '.join(
                'swarm-' + agent_type for agent_type in agent_types)))

    chosen_id = random.choice(list(cluster_ids))
    return all_clusters[chosen_id]


@pytest.fixture(scope='session', autouse=True)
def swarm_cluster():
    return pick_cluster([
        'swarm-discovery', 'swarm-procedure', 'swarm-labeling'])


@pytest.fixture(scope='session')
def swarm_service(swarm_cluster):
    from ..samples import delete_on_exit
    from .samples import create_service, delete_service

    resource = create_service(swarm_cluster)

    with delete_on_exit(resource, delete_service):
        yield resource
