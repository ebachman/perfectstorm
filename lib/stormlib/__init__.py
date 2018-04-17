import logging

from .models import (
    Agent,
    Application,
    Collection,
    Group,
    Procedure,
    Resource,
    Trigger,
)
from .session import connect


__all__ = [
    'Agent',
    'Application',
    'Collection',
    'Group',
    'Procedure',
    'Resource',
    'Trigger',
    'connect',
]

version_info = (0, 1)
__version__ = '0.1'


# Prevent warnings if logging is not configured
logging.getLogger(__name__).addHandler(logging.NullHandler())
del logging
