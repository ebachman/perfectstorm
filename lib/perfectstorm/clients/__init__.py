import abc
import argparse
import time
import traceback

from .. import DEFAULT_HOST, DEFAULT_PORT, connect


class BaseClient(metaclass=abc.ABCMeta):

    def create_parser(self, *args, **kwargs):
        self.parser = argparse.ArgumentParser(*args, **kwargs)
        self.add_arguments()

    def add_arguments(self):
        default_addr = '%s:%d' % (DEFAULT_HOST, DEFAULT_PORT)
        self.parser.add_argument(
            '-S', '--apiserver', metavar='HOST[:PORT]', default=default_addr,
            help='Address to the Perfect Storm API server (default: {})'.format(default_addr))

    def parse_arguments(self, args=None):
        self.create_parser()
        self.options = self.parser.parse_args(args)

    def setup_api(self):
        host, port = self.options.apiserver.rsplit(':', 1)
        port = int(port)
        connect(host, port)

    def setup(self, args=None):
        self.parse_arguments(args)
        self.setup_api()

    @abc.abstractmethod
    def main(self, args=None):
        raise NotImplementedError


class DaemonExecutor(BaseClient):

    def main(self, args=None):
        self.setup(args)

        try:
            while True:
                try:
                    self.wait()
                    self.run()
                except Exception as exc:
                    self.error(exc)
        except KeyboardInterrupt:
            pass

    @abc.abstractmethod
    def wait(self):
        raise NotImplementedError

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def error(self, exc):
        traceback.print_exception(type(exc), exc, exc.__traceback__)


class PollingExecutor(DaemonExecutor):

    poll_interval = 1

    def wait(self):
        while not self.poll():
            self.sleep()

    def sleep(self):
        time.sleep(self.poll_interval)

    @abc.abstractmethod
    def poll(self):
        raise NotImplementedError

    def error(self, exc):
        super().error(exc)
        self.sleep()
