import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--api-server-host', action='store', default='127.0.0.1',
        help='Host for the Perfect Storm API server')
    parser.addoption(
        '--api-server-port', action='store', type=int, default=8000,
        help='Host for the Perfect Storm API server')


@pytest.fixture(scope='session', autouse=True)
def api_session(request):
    import perfectstorm
    host = request.config.getoption('--api-server-host')
    port = request.config.getoption('--api-server-port')
    return perfectstorm.connect(host, port)


@pytest.fixture()
def agent():
    from perfectstorm import Agent

    agent = Agent(type='test')
    agent.save()

    yield agent

    agent.delete()