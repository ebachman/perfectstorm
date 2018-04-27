import json

from stormlib import Resource, Procedure

from ..samples import delete_on_exit
from ..stubs import random_name


def run_procedure(cluster_id, content):
    procedure = Procedure(
        type='swarm',
        content=json.dumps(content),
    )

    procedure.save()

    with delete_on_exit(procedure):
        procedure.exec(target=cluster_id)


def create_service(swarm_cluster):
    service_name = random_name()
    run_procedure(swarm_cluster.id, [
        'service create --name {} nginx:latest'.format(service_name),
    ])
    return Resource.objects.get(service_name)


def delete_service(resource):
    service_id = resource.snapshot['ID']
    run_procedure(resource.cluster, [
        'service rm {}'.format(service_id),
    ])
