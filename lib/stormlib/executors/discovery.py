import abc
import collections

from .base import AgentExecutor, PollingExecutor


SnapshotDiff = collections.namedtuple('SnapshotDiff', 'created updated deleted')


class DiscoveryExecutor(AgentExecutor, PollingExecutor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot = None

    def poll(self):
        curr_snapshot = self.take_current_snapshot()
        prev_snapshot = self.snapshot
        self.snapshot = curr_snapshot

        if prev_snapshot is None:
            prev_snapshot = self.take_stored_snapshot()

        diff = self.compare_snapshots(prev_snapshot, curr_snapshot)
        self.snapshot_diff = SnapshotDiff(*diff)
        self.snapshot = curr_snapshot

        return any(self.snapshot_diff)

    def run_inner(self):
        for resource_data in self.snapshot_diff.created:
            self.create_resource(resource_data)

        for resource_data in self.snapshot_diff.updated:
            self.update_resource(resource_data)

        for resource_data in self.snapshot_diff.deleted:
            self.delete_resource(resource_data)

    @abc.abstractmethod
    def take_current_snapshot(self):
        raise NotImplementedError

    @abc.abstractmethod
    def take_stored_snapshot(self):
        raise NotImplementedError

    @abc.abstractmethod
    def compare_snapshots(self, prev, curr):
        raise NotImplementedError

    @abc.abstractmethod
    def create_resource(self, resource_data):
        raise NotImplementedError

    @abc.abstractmethod
    def update_resource(self, resource_data):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_resource(self, resource_data):
        raise NotImplementedError
