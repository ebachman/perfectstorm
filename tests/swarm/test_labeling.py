import random
import time

import pytest

from stormlib import Resource, Group

from ..stubs import random_name
from .samples import create_service, delete_service


def check_labeling(resources):
    # Pick a random group/label name
    group_name = random_name()
    label_name = 'storm-group-' + group_name

    # Check that no resource has the label we want to assign
    assert not any(
        label_name in resource.snapshot['Spec']['Labels']
        for resource in resources)

    # Pick a random resource and define a group containing it
    target_resource = random.choice(resources)
    other_resources = [
        resource for resource in resources
        if resource is not target_resource
    ]

    group = Group(name=group_name, include=[target_resource.id])
    group.save()

    # After some time, the resource should be assigned the label. Wait at most
    # 10 seconds.
    max_time = time.time() + 10
    while time.time() < max_time:
        target_resource.reload()
        if label_name in target_resource.snapshot['Spec']['Labels']:
            break
        time.sleep(.5)

    assert target_resource.snapshot['Spec']['Labels'][label_name] == 'yes'

    # No other resource should have this label
    for resource in other_resources:
        resource.reload()
        assert label_name not in resource.snapshot['Spec']['Labels']

    # Remove the group. The label should be removed.
    group.delete()

    max_time = time.time() + 10
    while time.time() < max_time:
        target_resource.reload()
        if label_name not in target_resource.snapshot['Spec']['Labels']:
            break
        time.sleep(.5)

    assert label_name not in target_resource.snapshot['Spec']['Labels']


def test_service_labeling(swarm_cluster):
    services = [create_service(swarm_cluster) for i in range(2)]

    try:
        check_labeling(services)
    finally:
        for resource in services:
            delete_service(resource)


def test_node_labeling(swarm_cluster):
    nodes = Resource.objects.filter(
        type='swarm-node', parent=swarm_cluster.id)

    if len(nodes) < 2:
        pytest.skip('swarm cluster too small (at least 2 nodes required )')

    check_labeling(nodes)
