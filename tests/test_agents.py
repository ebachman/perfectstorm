from perfectstorm import Agent

from .create import BaseTestCreate
from .stubs import ANY, IDENTIFIER


class TestCreate(BaseTestCreate):

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
