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

from setuptools import setup, find_packages

setup(
    name='perfectstorm-core',
    version='0.1',
    packages=find_packages(),
    package_data={
        'teacup.docs': [
            'source/*.rst',
            'source/conf.py',
        ],
    },
    scripts=['stormd'],
    install_requires=[
        'Django >= 1.11, < 1.12',
        'PyYAML >= 3.12, < 4',
        'Sphinx >= 1.6.5, < 1.7',
        'django-rest-framework-mongoengine >= 3.3, < 3.4',
        'djangorestframework >= 3.7, < 3.8',
        'gevent >= 1.2, < 1.3',
        'jsonfield >= 2, < 3',
        'mongoengine >= 0.15, < 0.16',
        'pymongo >= 3.6, < 3.7',
        'requests >= 2.13, < 3',
        'requests_toolbelt >= 0.7, < 1',
        'tornado >= 4.5, < 4.6',
    ],
    zip_safe=False,
)
