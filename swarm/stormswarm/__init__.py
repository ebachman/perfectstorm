import requests


class Swarm:

    def __init__(self, address):
        self.address = address
        self._cluster_id = None

    def get(self, path):
        url = 'http://{}/{}'.format(self.address, path)
        response = requests.get(url)
        response.raise_for_status()
        return response

    def post(self, path, **kwargs):
        url = 'http://{}/{}'.format(self.address, path)
        response = requests.post(url, **kwargs)
        response.raise_for_status()
        return response

    @property
    def cluster_id(self):
        if self._cluster_id is None:
            data = self.get('info').json()
            self._cluster_id = data['Swarm']['Cluster']['ID']
        return self._cluster_id


class SwarmMixin:

    def __init__(self, swarm, *args, **kwargs):
        self.swarm = swarm
        super().__init__(*args, **kwargs)
