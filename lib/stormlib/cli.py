import abc
import argparse
import logging.config
import sys

from . import session


class LogFormatter(logging.Formatter):

    def format(self, record):
        if record.levelno == logging.INFO:
            record.levelprefix = ''
        else:
            record.levelprefix = record.levelname + ': '
        return super().format(record)


class LogLevelFilter(logging.Filter):

    def __init__(self, stop_level):
        self.stop_level = stop_level

    def filter(self, record):
        return record.levelno < self.stop_level


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
        level = logging.DEBUG if self.options.debug else logging.INFO

        formatter = LogFormatter(fmt='%(levelprefix)s%(message)s')

        out_handler = logging.StreamHandler(stream=sys.stdout)
        out_handler.addFilter(LogLevelFilter(logging.WARNING))
        out_handler.setFormatter(formatter)
        out_handler.setLevel(level)

        err_handler = logging.StreamHandler(stream=sys.stderr)
        out_handler.setFormatter(formatter)
        err_handler.setLevel(logging.WARNING)

        loggers = getattr(self, 'configure_loggers', [])
        loggers = ('stormlib', *loggers)

        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            logger.addHandler(out_handler)
            logger.addHandler(err_handler)


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
