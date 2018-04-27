import time

from stormlib import Resource

from .samples import run_procedure


def test_service_create(swarm_service):
    assert swarm_service.type == 'swarm-service'
    assert swarm_service.status == 'running'

    swarm_tasks = Resource.objects.filter(
        type='swarm-task',
        parent=swarm_service.id,
    )
    assert len(swarm_tasks) == 1

    swarm_task, = swarm_tasks
    assert swarm_task.status == 'running'
    assert swarm_task.cluster == swarm_service.cluster
    assert swarm_task.host is not None


def test_service_exec(swarm_service):
    # Check that the task is initially running
    swarm_task = Resource.objects.get(
        type='swarm-task',
        parent=swarm_service.id,
    )
    assert swarm_task.status == 'running'

    # Create and run a procedure to kill the init process (PID 1).
    # If it works, this should cause the task to quit.
    run_procedure(swarm_service.cluster, [
        'service exec {} sh -c "kill 1"'.format(swarm_task.snapshot['ID']),
    ])

    # Wait for the task to quit, for at most 10 seconds.
    max_time = time.time() + 10
    while swarm_task.status == 'running':
        if time.time() > max_time:
            break
        time.sleep(.5)
        swarm_task.reload()

    assert swarm_task.status == 'stopped'
