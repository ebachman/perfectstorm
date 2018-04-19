from stormlib import Agent

from .create import BaseTestCreate
from .stubs import ANY, IDENTIFIER, random_name


class TestCreate(BaseTestCreate):

    model = Agent

    @property
    def valid_data(self):
        # This is a property so that random_name() can return a new value
        # every time this attribute is accessed.
        return [
            (
                {'type': 'test'},
                {
                    'id': IDENTIFIER,
                    'type': 'test',
                    'name': None,
                    'status': 'offline',
                    'heartbeat': ANY,
                },
            ),
            (
                {'type': 'test', 'name': random_name()},
                {
                    'id': IDENTIFIER,
                    'type': 'test',
                    'name': random_name.last,
                    'status': 'offline',
                    'heartbeat': ANY,
                },
            ),
            (
                {'type': 'test', 'name': random_name(), 'status': 'offline'},
                {
                    'id': IDENTIFIER,
                    'type': 'test',
                    'name': random_name.last,
                    'status': 'offline',
                    'heartbeat': ANY,
                },
            ),
            (
                {'type': 'test', 'name': random_name(), 'status': 'online'},
                {
                    'id': IDENTIFIER,
                    'type': 'test',
                    'name': random_name.last,
                    'status': 'online',
                    'heartbeat': ANY,
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
