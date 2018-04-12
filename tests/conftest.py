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
    from perfectstorm import Agent, Application, Group, Procedure

    yield

    if request.config.getoption('--no-cleanup'):
        return

    delete = []

    delete.extend(Agent.objects.filter(type='test'))
    delete.extend(Group.objects.all())
    delete.extend(Application.objects.all())
    delete.extend(Procedure.objects.all())
    # No need to delete resources: they will be deleted
    # automatically when deleting the agents

    for obj in delete:
        obj.delete()


@pytest.fixture()
def agent(request):
    from .samples import create_agent
    agent = create_agent()
    yield agent
    agent.delete()


@pytest.fixture(scope='session')
def random_resources():
    from .samples import create_random_resources
    return create_random_resources()
