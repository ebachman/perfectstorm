from perfectstorm import Resource


def test_discovery(swarm_cluster, swarm_service):
    # Check all the Swarm services in this cluster
    swarm_services = Resource.objects.filter(parent=swarm_cluster.id)
    for service in swarm_services:
        assert service.type == 'swarm-service'

        # Check all the tasks for this service
        swarm_tasks = Resource.objects.filter(parent=service.id)
        for task in swarm_tasks:
            assert task.type == 'swarm-task'

    # Check the service created by us
    assert len(swarm_service.names) == 2
    service_name, service_id = swarm_service.names
    assert swarm_service.status == 'running'
    assert swarm_service.health == 'healthy'

    # Check the task created by us
    task = Resource.objects.get(parent=swarm_service.id)

    assert task.type == 'swarm-task'
    assert task.owner == swarm_service.owner
    assert (service_name + '.1') in task.names
    assert task.snapshot['ID'] in task.names
    assert task.status == 'running'
    assert task.health == 'healthy'
    assert task.image.startswith('library/nginx:latest@')
