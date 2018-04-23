from stormlib import Resource, Procedure

from ..stubs import random_name


def create_service(swarm_cluster):
    service_name = random_name()

    create_procedure = Procedure(
        type='swarm',
        content={
            'run': [
                'service create --name {} nginx:latest'.format(service_name),
            ],
        },
    )
    create_procedure.save()

    job = create_procedure.exec(target=swarm_cluster.id)
    job.wait()

    create_procedure.delete()

    return Resource.objects.get(service_name)


def delete_service(resource):
    service_id = resource.snapshot['ID']

    rm_procedure = Procedure(
        type='swarm',
        content={
            'run': [
                'service rm {}'.format(service_id),
            ],
        },
    )
    rm_procedure.save()

    job = rm_procedure.exec(target=resource.parent)
    job.wait()

    rm_procedure.delete()
