import abc
import argparse
import logging.config
import sys

from . import session


class CommandLineClient(metaclass=abc.ABCMeta):

    def __init__(self, args=None):
        self.args = args if args is not None else sys.argv[1:]

    def main(self):
        self.setup()
        try:
            self.run()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.teardown()

    @abc.abstractmethod
    def run(self):
        raise NotImplementedError

    def setup(self):
        self.parse_arguments()
        self.connect_api()
        self.setup_logging()

    def teardown(self):
        pass

    def handle_error(self, exc):
        raise exc

    def parse_arguments(self):
        parser = self.get_argument_parser()
        self.options = parser.parse_args(self.args)

    def get_argument_parser(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)
        return parser

    def add_arguments(self, parser):
        default_addr = '%s:%d' % (session.DEFAULT_HOST, session.DEFAULT_PORT)
        parser.add_argument(
            '-C', '--connect', metavar='HOST[:PORT]', default=default_addr,
            help='Address to the Perfect Storm API '
                 'Server (default: {})'.format(default_addr))
        parser.add_argument(
            '-D', '--debug', action='store_true',
            help='Show debug logs')

    def connect_api(self):
        host, port = self.options.connect.rsplit(':', 1)
        port = int(port)
        session.connect(host, port)

    def setup_logging(self):
        if not self.options.debug:
            return

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
                'stormlib': {
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': True
                },
            },
        })


class AgentClient(CommandLineClient):

    def setup(self):
        super().setup()
        self.setup_agent()

    def setup_agent(self):
        self.agent = self.get_agent()

        if self.agent.id is None:
            self.agent.id = self.agent.name

        self.agent.status = 'online'
        self.agent.save()
        self.agent.heartbeat.start()

    def teardown(self):
        self.teardown_agent()
        super().teardown()

    def teardown_agent(self):
        self.agent.heartbeat.stop()
        self.agent.status = 'offline'
        self.agent.save()
