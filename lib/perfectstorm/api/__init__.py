import json

import requests

from . import base, shortcuts
from .resources import Group, Application, Recipe, Trigger


__all__ = [
    'ApiClient',
    'Group',
    'Application',
    'Recipe',
    'Trigger',
]


DEFAULT_APISERVER = 'http://127.0.0.1:8000/'


class PerfectStormApi(base.RestMixin):

    path = '/'

    def __init__(self, url=None):
        if url is None:
            url = DEFAULT_APISERVER
        self.server_url = url

    groups = Group.as_collection()
    apps = Application.as_collection()
    recipes = Recipe.as_collection()
    triggers = Trigger.as_collection()
    shortcuts = shortcuts.Shortcuts()

    def query(self, *args, **kwargs):
        q = dict(*args, **kwargs)
        json_q = json.dumps(q)
        return self._get('v1/query/', params={'q': json_q})
