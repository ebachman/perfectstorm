# Copyright (c) 2017, Composure.ai
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

import json

import requests

from . import base, shortcuts
from .resources import Resource, Group, Application, Recipe, Trigger


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

    resources = Resource.as_collection()
    groups = Group.as_collection()
    apps = Application.as_collection()
    recipes = Recipe.as_collection()
    triggers = Trigger.as_collection()
    shortcuts = shortcuts.Shortcuts()

    def query(self, *args, **kwargs):
        q = dict(*args, **kwargs)
        json_q = json.dumps(q)
        return self._get('v1/query/', params={'q': json_q})
