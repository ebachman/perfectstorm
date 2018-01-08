# Copyright (c) 2018, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

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
