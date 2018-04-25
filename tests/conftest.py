import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--api-server-host', action='store', default='127.0.0.1',
        help='Host for the Perfect Storm API server')
    parser.addoption(
        '--api-server-port', action='store', type=int, default=28482,
        help='Host for the Perfect Storm API server')
    parser.addoption(
        '--no-cleanup', action='store_true',
        help='Keep all API entities created during tests')


@pytest.fixture(scope='session', autouse=True)
def api_session(request):
    import stormlib
    host = request.config.getoption('--api-server-host')
    port = request.config.getoption('--api-server-port')
    return stormlib.connect(host, port)


@pytest.fixture(scope='session', autouse=True)
def cleanup(request):
    from stormlib import (
        Agent, Application, Group, Procedure, Subscription, Job)
    from . import samples

    samples.CLEANUP = not request.config.getoption('--no-cleanup')

    yield

    if not samples.CLEANUP:
        return

    delete = []

    delete.extend(Agent.objects.filter(type='test'))
    delete.extend(Group.objects.all())
    delete.extend(Application.objects.all())
    delete.extend(Procedure.objects.all())
    delete.extend(Subscription.objects.all())
    delete.extend(Job.objects.all())
    # No need to delete resources: they will be deleted
    # automatically when deleting the agents

    for obj in delete:
        obj.delete()


@pytest.fixture()
def agent():
    from .samples import create_agent, delete_on_exit
    with delete_on_exit(create_agent()) as agent:
        yield agent


@pytest.fixture(scope='session')
def random_resources():
    from .samples import create_random_resources, delete_on_exit
    with delete_on_exit(create_random_resources()) as resources:
        yield resources


@pytest.fixture()
def resource(agent):
    from .samples import create_random_resources, delete_on_exit
    lst = create_random_resources(
        count=1,
        min_running_percent=0,
        min_healthy_percent=0,
        owner=agent.id,
    )
    with delete_on_exit(lst):
        yield lst[0]


@pytest.fixture()
def alpha_group():
    from .samples import create_group, delete_on_exit
    group = create_group(query={'type': 'alpha'})
    with delete_on_exit(group) as group:
        yield group


@pytest.fixture()
def procedure():
    from .samples import create_procedure, delete_on_exit
    with delete_on_exit(create_procedure()) as procedure:
        yield procedure
