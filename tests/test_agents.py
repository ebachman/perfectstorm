from perfectstorm import Agent

from .stubs import ANY, IDENTIFIER
from .test_create import BaseTestDocumentCreation


class TestAgentCreation(BaseTestDocumentCreation):

    model = Agent

    valid_data = [
        (
            {'type': 'test'},
            {'id': IDENTIFIER, 'type': 'test', 'heartbeat': ANY},
        ),
    ]

    invalid_data = [
        (
            {},
            'type: field cannot be None',
            {'type': ['This field is required.']},
        ),
    ]
