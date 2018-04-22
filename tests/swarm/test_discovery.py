from stormlib import Resource


def test_service_discovery(swarm_cluster, swarm_service):
    # Check all the Swarm services in this cluster
    swarm_services = Resource.objects.filter(
        parent=swarm_cluster.id, type='swarm-service')
    assert len(swarm_services) > 0

    for service in swarm_services:
        assert service.type == 'swarm-service'
        # Services should have two names: Docker name and Docker ID
        assert len(service.names) == 2

        assert 'Spec' in service.snapshot
        assert 'TaskTemplate' in service.snapshot['Spec']

        # Check all the tasks for this service
        swarm_tasks = Resource.objects.filter(parent=service.id)
        assert len(swarm_tasks) > 0

        for task in swarm_tasks:
            assert task.type == 'swarm-task'
            # Tasks should have three to four names:
            # - <service_name>.<suffix>
            # - <service_name>.<suffix>.<task_id>
            # - <task_id>
            # - <container_id> (this one is not available if no container
            #   exists yet)
            assert 3 <= len(task.names) <= 4

            assert 'Spec' in task.snapshot
            assert 'ContainerSpec' in task.snapshot['Spec']

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
    assert (
        task.image == 'library/nginx:latest' or
        task.image.startswith('library/nginx:latest@'))


def test_node_discovery(swarm_cluster):
    swarm_nodes = Resource.objects.filter(
        parent=swarm_cluster.id, type='swarm-node')
    assert len(swarm_nodes) > 0

    for node in swarm_nodes:
        assert node.type == 'swarm-node'
        # Services should have two names: hostname and Docker ID
        assert len(node.names) == 2

        assert 'Description' in node.snapshot
        assert 'Engine' in node.snapshot['Description']
