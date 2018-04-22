import os
import pathlib

import pytest


@pytest.fixture(scope='session', autouse=True)
def skip_without_stormctl(request, api_session):
    """Skip the execution of tests if stormctl is not in $PATH."""
    for path in os.get_exec_path():
        name = os.path.join(path, 'stormctl')
        if os.access(name, os.X_OK):
            return
    pytest.skip('stormctl not found')


@pytest.fixture(scope='session')
def examples_path():
    import tests

    test_package_path = pathlib.Path(tests.__file__).parent
    examples_path = test_package_path.parent / 'examples'

    if examples_path.is_dir():
        return examples_path

    pytest.skip('examples directiory not found')


# Fixtures borrowed from tests.swarm

@pytest.fixture(scope='session')
def skip_without_swarm(request, api_session):
    from ..swarm.conftest import skip_without_swarm
    skip_without_swarm(request, api_session)


@pytest.fixture(scope='session')
def swarm_cluster(skip_without_swarm):
    from ..swarm.conftest import swarm_cluster
    return swarm_cluster()
