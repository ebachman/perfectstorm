import abc

from stormlib import Agent
from stormlib.cli import AgentClient

from . import Swarm


class SwarmClient(AgentClient):

    @property
    @abc.abstractmethod
    def role(self):
        raise NotImplementedError

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '-H', '--host', metavar='HOST[:PORT]', required=True,
            help='Docker daemon to connect to')

    def get_agent(self):
        self.swarm = Swarm(self.options.host)

        return Agent(
            type='-'.join(('swarm', self.role)),
            name='-'.join(('swarm', self.role, self.swarm.cluster_id)),
            options={
                'host': self.options.host,
                'clusterId': self.swarm.cluster_id,
            },
        )
