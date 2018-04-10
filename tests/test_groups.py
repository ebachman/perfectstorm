import pytest

from perfectstorm import Group
from perfectstorm.exceptions import APIRequestError

from .stubs import IDENTIFIER
from .test_create import BaseTestDocumentCreation


class TestGroupCreation(BaseTestDocumentCreation):

    model = Group

    default_group = {
        'id': IDENTIFIER,
        'name': None,
        'query': {},
        'services': [],
        'include': [],
        'exclude': [],
    }

    valid_data = [
        (
            {},
            default_group,
        ),
        (
            {'name': 'test'},
            {**default_group, 'name': 'test'},
        ),

        # Simple query

        (
            {'query': {'x': 'y'}},
            {**default_group, 'query': {'x': 'y'}},
        ),

        # Nested query

        (
            {'query': {'x': [{'y': 'z'}, 1, 2, 3]}},
            {**default_group, 'query': {'x': [{'y': 'z'}, 1, 2, 3]}},
        ),

        # Queries containing special characters

        (
            {'query': {'a.b': 'c'}},
            {**default_group, 'query': {'a.b': 'c'}},
        ),
        (
            {'query': {'a$b': 'c'}},
            {**default_group, 'query': {'a$b': 'c'}},
        ),
        (
            {'query': {'a\0b': 'c'}},
            {**default_group, 'query': {'a\0b': 'c'}},
        ),
    ]

    def test_duplicate_names(self):
        group1 = Group(name='x')
        group2 = Group(name='x')

        group1.save()

        with pytest.raises(APIRequestError) as excinfo:
            group2.save()

        assert excinfo.value.response.json() == {
            'name': ['This field must be unique.'],
        }
