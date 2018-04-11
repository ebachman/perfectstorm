import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--api-server-host', action='store', default='127.0.0.1',
        help='Host for the Perfect Storm API server')
    parser.addoption(
        '--api-server-port', action='store', type=int, default=8000,
        help='Host for the Perfect Storm API server')
    parser.addoption(
        '--no-cleanup', action='store_true',
        help='Keep all API entities created during tests')


@pytest.fixture(scope='session', autouse=True)
def api_session(request):
    import perfectstorm
    host = request.config.getoption('--api-server-host')
    port = request.config.getoption('--api-server-port')
    return perfectstorm.connect(host, port)


@pytest.fixture(scope='session', autouse=True)
def cleanup(request):
    import perfectstorm.api.base
    import perfectstorm.api.models

    yield

    if request.config.getoption('--no-cleanup'):
        return

    for name in perfectstorm.api.models.__all__:
        cls = getattr(perfectstorm.api.models, name)
        if not isinstance(cls, type) or not issubclass(cls, perfectstorm.api.base.Model):
            continue
        for obj in cls.objects.all():
            obj.delete()


@pytest.fixture()
def agent(request):
    from perfectstorm import Agent

    agent = Agent(type='test')
    agent.save()

    yield agent

    if request.config.getoption('--no-cleanup'):
        return

    agent.delete()
