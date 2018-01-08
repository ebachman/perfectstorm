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

from . import api


class CommandLineClient(metaclass=abc.ABCMeta):

    def __init__(self, args=None):
        self.args = args if args is not None else sys.argv[1:]

    @classmethod
    def main(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        self.setup()
        try:
            self.run()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            self.on_error(exc)
            sys.exit(1)
        finally:
            self.teardown()
        sys.exit()

    def setup(self):
        self.parse_arguments()
        self.connect_api()

    def teardown(self):
        pass

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def on_error(self, exc):
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def parse_arguments(self):
        parser = self.get_argument_parser()
        self.options = parser.parse_args(self.args)

    def get_argument_parser(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)
        return parser

    def add_arguments(self, parser):
        default_addr = '%s:%d' % (api.DEFAULT_HOST, api.DEFAULT_PORT)
        parser.add_argument(
            '-C', '--connect', metavar='HOST[:PORT]', default=default_addr,
            help='Address to the Perfect Storm API server (default: {})'.format(default_addr))

    def connect_api(self):
        host, port = self.options.connect.rsplit(':', 1)
        port = int(port)
        api.connect(host, port)


class DaemonClient(CommandLineClient):

    restart_interval = 1

    @classmethod
    def main(cls, *args, **kwargs):
        self = cls(**kwargs)
        self.setup()
        try:
            while True:
                try:
                    self.run()
                except Exception as exc:
                    self.on_error(exc)
                time.sleep(self.restart_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self.teardown()
        sys.exit()


class ExecutorClient(CommandLineClient):

    def get_executor(self):
        executor_class = getattr(self, 'executor_class', None)
        if executor_class is None:
            raise NotImplementedError('Subclasses must set executor_class or override get_executor()')
        return executor_class()

    def run(self):
        executor = self.get_executor()
        executor.run()
