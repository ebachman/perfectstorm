import json

from stormlib import Resource, Procedure

from ..stubs import random_name


def create_service(swarm_cluster):
    service_name = random_name()

    create_procedure = Procedure(
        type='swarm',
        content=json.dumps([
            'service create --name {} nginx:latest'.format(service_name),
        ]),
    )
    create_procedure.save()

    create_procedure.exec(target=swarm_cluster.id)

    create_procedure.delete()

    return Resource.objects.get(service_name)


def delete_service(resource):
    service_id = resource.snapshot['ID']

    rm_procedure = Procedure(
        type='swarm',
        content=json.dumps([
            'service rm {}'.format(service_id),
        ]),
    )
    rm_procedure.save()

    rm_procedure.exec(target=resource.parent)

    rm_procedure.delete()
