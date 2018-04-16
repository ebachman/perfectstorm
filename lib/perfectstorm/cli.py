import abc
import argparse
import logging.config
import sys
import time
import traceback

from . import api
from .api import Agent
from .executors import RestartingProcessExecutorRunner


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
        if self.options.debug:
            self.enable_debug()

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
        parser.add_argument(
            '-D', '--debug', action='store_true',
            help='Show debug logs')

    def connect_api(self):
        host, port = self.options.connect.rsplit(':', 1)
        port = int(port)
        api.connect(host, port)

    def enable_debug(self):
        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '[%(levelname)s] %(message)s'
                },
            },
            'handlers': {
                'default': {
                    'level': 'DEBUG',
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                'perfectstorm': {
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': True
                },
            },
        })


class DaemonClient(CommandLineClient):

    restart_interval = 1

    @classmethod
    def main(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
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


class AgentClient(DaemonClient):

    @property
    @abc.abstractmethod
    def agent_type(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = None

    def setup(self):
        super().setup()
        self.agent = Agent(type=self.agent_type)
        self.agent.save()
        self.agent.heartbeat.start()

    def teardown(self):
        super().teardown()
        self.agent.heartbeat.stop()
        self.agent.delete()
        self.agent = None


class ExecutorClient(AgentClient):

    def get_executors(self):
        executor_classes = getattr(self, 'executor_classes', None)
        if executor_classes is None:
            raise NotImplementedError('Subclasses must set executor_classes or override get_executors()')
        return [cls() for cls in executor_classes]

    def get_runner(self):
        runner_class = getattr(self, 'runner_class', None)
        if runner_class is None:
            runner_class = RestartingProcessExecutorRunner
        executors = self.get_executors()
        return runner_class(executors)

    def run(self):
        runner = self.get_runner()
        runner.dispatch()
        runner.wait()
