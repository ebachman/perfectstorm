import os

import pytest


@pytest.fixture(scope='session', autouse=True)
def skip_without_stormctl(request, api_session):
    """Skip the execution of tests if stormctl is not in $PATH."""
    for path in os.get_exec_path():
        name = os.path.join(path, 'stormctl')
        if os.access(name, os.X_OK):
            return
    pytest.skip('stormctl not found')
