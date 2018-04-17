import abc
import collections

from . import PollingExecutor


class Diff(collections.namedtuple('Diff', 'added deleted updated')):

    def __bool__(self):
        return any(self)


class frozendict(dict):

    __setitem__ = None
    __delitem__ = None

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            pass

        self._hash = hash(frozenset(self.items()))
        return self._hash

    def __repr__(self):
        return 'frozendict({})'.format(super().__repr__())


def freeze(obj):
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (tuple, list)):
        return tuple(freeze(item) for item in obj)
    elif isinstance(obj, (set, frozenset)):
        return frozenset(freeze(item) for item in obj)
    elif isinstance(obj, dict):
        return frozendict(freeze(item) for item in obj.items())
    else:
        raise TypeError(type(obj).__name__)


def collection_diff(past_set, present_set, idfunc=None):
    if past_set == present_set:
        return Diff(set(), set(), set())

    if idfunc is None:
        idfunc = id

    past_map = {idfunc(item): item for item in past_set}
    present_map = {idfunc(item): item for item in present_set}

    added_elems = set()
    deleted_elems = set()
    updated_elems = set()
    all_elems = past_set | present_set

    for item in all_elems:
        itemid = idfunc(item)

        if itemid not in past_map:
            added_elems.add(item)
        elif itemid not in present_map:
            deleted_elems.add(item)
        elif past_map[itemid] != present_map[itemid]:
            updated_elems.add(item)

    return Diff(added_elems, deleted_elems, updated_elems)


class CollectionMonitor(metaclass=abc.ABCMeta):

    def __init__(self):
        self._prev_snapshot = frozenset()
        self._cur_snapshot = frozenset()
        self._changes = None

    def refresh(self):
        self._prev_snapshot = self._cur_snapshot
        self._cur_snapshot = frozenset(freeze(self.get_latest_items()))
        self._changes = None

    def get_changes(self):
        if self._changes is None:
            self._changes = self.compute_changes()
        return self._changes

    def has_changed(self):
        return bool(self.get_changes())

    def compute_changes(self):
        past_items = self._prev_snapshot
        present_items = self._cur_snapshot
        return collection_diff(past_items, present_items, idfunc=self.get_item_id)

    @abc.abstractmethod
    def get_latest_items(self):
        return []

    @abc.abstractmethod
    def get_item_id(self):
        return []


class GroupMembersMonitor(CollectionMonitor):

    def __init__(self, group):
        super().__init__()
        self.group = group

    def get_latest_items(self):
        return self.group.members()

    def get_item_id(self, item):
        return item['cloud_id']


class ResourceMonitor(CollectionMonitor):

    @property
    @abc.abstractmethod
    def resource_name(self):
        raise NotImplementedError

    def __init__(self, api):
        super().__init__()
        self.api = api

    def get_latest_items(self):
        resource = getattr(self.api, self.resource_name)
        return [item.data for item in resource.all()]

    def get_item_id(self, item):
        return item['name']


class GroupsMonitor(ResourceMonitor):

    resource_name = 'groups'


class ApplicationsMonitor(ResourceMonitor):

    resource_name = 'apps'


class MonitorPollingExecutor(PollingExecutor):

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.monitors = []
        self.setup_monitors()

    @abc.abstractmethod
    def setup_monitors(self):
        raise NotImplementedError

    def poll(self):
        for monitor in self.monitors:
            monitor.refresh()
        return any(monitor.has_changed() for monitor in self.monitors)
