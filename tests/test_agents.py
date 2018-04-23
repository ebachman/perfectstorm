from stormlib import Agent

from .create import BaseTestCreate
from .stubs import ANY, IDENTIFIER, PLACEHOLDER, random_name


class TestCreate(BaseTestCreate):

    model = Agent

    default_agent = {
        'id': IDENTIFIER,
        'type': PLACEHOLDER,
        'name': None,
        'status': 'offline',
        'options': {},
        'heartbeat': ANY,
    }

    @property
    def valid_data(self):
        # This is a property so that random_name() can return a new value
        # every time this attribute is accessed.
        return [
            (
                {'type': 'test'},
                {**self.default_agent, 'type': 'test'},
            ),
            (
                {'type': 'test', 'name': random_name()},
                {
                    **self.default_agent,
                    'type': 'test',
                    'name': random_name.last,
                },
            ),
            (
                {'type': 'test', 'name': random_name(), 'status': 'offline'},
                {
                    **self.default_agent,
                    'type': 'test',
                    'name': random_name.last,
                    'status': 'offline',
                },
            ),
            (
                {'type': 'test', 'name': random_name(), 'status': 'online'},
                {
                    **self.default_agent,
                    'type': 'test',
                    'name': random_name.last,
                    'status': 'online',
                },
            ),
            (
                {'type': 'test', 'options': {'x': 'y'}},
                {
                    **self.default_agent,
                    'type': 'test',
                    'options': {'x': 'y'},
                },
            ),
        ]

    invalid_data = [
        (
            {},
            'type: Field cannot be None',
            {
                'type': ['This field is required.'],
            },
        ),
    ]

    invalid_server_only_data = [
        (
            {'type': 'test', 'status': 'invalid'},
            {
                'status': ['"invalid" is not a valid choice.'],
            },
        ),
    ]
