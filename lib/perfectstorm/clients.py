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

import abc
import argparse
import sys
import time
import traceback

from . import base


class BaseClient(metaclass=abc.ABCMeta):

    exit_on_error = False

    def main(self, args=None):
        self.setup(args)

        try:
            while True:
                try:
                    self.run()
                except Exception as exc:
                    self.error(exc)
        except KeyboardInterrupt:
            pass
        finally:
            self.teardown()

        sys.exit(0)

    def setup(self, args=None):
        self.parse_arguments(args)

    def parse_arguments(self, args=None):
        parser = self.get_argument_parser()
        self.options = parser.parse_args(args)

    def get_argument_parser(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)
        return parser

    def add_arguments(self, parser):
        pass

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def teardown(self):
        pass

    def error(self, exc):
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        if self.exit_on_error:
            sys.exit(1)
        else:
            time.sleep(1)


class APIClient(BaseClient):

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.connect_api()

    def add_arguments(self, parser):
        super().add_arguments(parser)

        default_addr = '%s:%d' % (base.DEFAULT_HOST, base.DEFAULT_PORT)
        parser.add_argument(
            '-S', '--apiserver', metavar='HOST[:PORT]', default=default_addr,
            help='Address to the Perfect Storm API server (default: {})'.format(default_addr))

    def connect_api(self):
        host, port = self.options.apiserver.rsplit(':', 1)
        port = int(port)
        base.connect(host, port)
