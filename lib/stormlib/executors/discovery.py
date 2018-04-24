import abc
import collections
import functools

from .. import Resource
from .base import AgentExecutorMixin, PollingExecutor


ResourceSnapshot = collections.namedtuple(
    'ResourceSnapshot', 'type internal_id data')


class DiscoveryProbe(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def resource_type(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_snapshots(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_internal_id(self, resource_data):
        raise NotImplementedError

    @abc.abstractmethod
    def model_resource(self, resource_data):
        raise NotImplementedError

    def save_resource(self, resource):
        resource.save()

    def delete_resource(self, resource):
        resource.save()


class DiscoveryExecutor(AgentExecutorMixin, PollingExecutor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshots = None
        self.probes = {
            probe.resource_type: probe
            for probe in self.get_probes()
        }

    @property
    def get_probes(self):
        raise NotImplementedError

    def poll_jobs(self):
        curr_snapshot_items = self.get_snapshots()
        curr_snapshots = {
            item.internal_id: item for item in curr_snapshot_items}

        prev_snapshots = self.snapshots
        self.snapshots = curr_snapshots

        if prev_snapshots is None:
            prev_snapshot_items = self.get_stored_snapshots()
            prev_snapshots = {
                item.internal_id: item for item in prev_snapshot_items}

        changes = self.compare_snapshots(prev_snapshots, curr_snapshots)

        for modification, resource_snapshot in changes:
            func = getattr(self, 'resource_{}'.format(modification))
            yield functools.partial(func, *resource_snapshot)

    def get_snapshots(self):
        for probe in self.probes.values():
            for data in probe.get_snapshots():
                yield ResourceSnapshot(
                    probe.resource_type,
                    probe.get_internal_id(data),
                    data)

    def get_stored_snapshots(self):
        for res in Resource.objects.filter(owner=self.agent.id):
            try:
                probe = self.probes[res.type]
            except KeyError:
                internal_id = res.id
            else:
                internal_id = probe.get_internal_id(res.snapshot)
            yield ResourceSnapshot(
                res.type,
                internal_id,
                res.snapshot)

    def compare_snapshots(self, prev, curr):
        changes = []

        for res_id, prev_snapshot in prev.items():
            if res_id not in curr:
                changes.append(('deleted', prev_snapshot))

        for res_id, curr_snapshot in curr.items():
            if res_id not in prev:
                changes.append(('created', curr_snapshot))
            else:
                prev_snapshot = prev[res_id]
                if prev_snapshot != curr_snapshot:
                    changes.append(('updated', curr_snapshot))

        return changes

    def resource_created(self, resource_type, resource_id, resource_data):
        obj = self.model_resource(resource_type, resource_id, resource_data)
        probe = self.probes[resource_type]
        probe.save_resource(obj)

    def resource_updated(self, resource_type, resource_id, resource_data):
        obj = self.model_resource(resource_type, resource_id, resource_data)
        # Ensure that obj has an ID, otherwise a new Resource will
        # be created
        if obj.id is None:
            obj.id = resource_id
        probe = self.probes[resource_type]
        probe.save_resource(obj)

    def model_resource(self, resource_type, resource_id, resource_data):
        probe = self.probes[resource_type]
        obj = probe.model_resource(resource_data)
        obj.owner = self.agent.id
        obj.type = resource_type
        obj.snapshot = resource_data
        return obj

    def save_resource(self, obj):
        obj.save()

    def resource_deleted(self, resource_type, resource_id, resource_data):
        obj = Resource(id=resource_id)
        probe = self.probes[resource_type]
        probe.delete_resource(obj)
