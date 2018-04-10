import pytest

from perfectstorm import Group
from perfectstorm.exceptions import APIRequestError

from .stubs import IDENTIFIER, random_name
from .test_create import BaseTestDocumentCreation


class TestCreate(BaseTestDocumentCreation):

    model = Group

    default_group = {
        'id': IDENTIFIER,
        'name': None,
        'query': {},
        'services': [],
        'include': [],
        'exclude': [],
    }

    @property
    def valid_data(self):
        # This is a property so that random_name() can return a new value
        # every time this attribute is accessed.
        return [
            (
                {},
                self.default_group,
            ),
            (
                {'name': random_name()},
                {**self.default_group, 'name': random_name.last},
            ),

            # Simple query

            (
                {'query': {'x': 'y'}},
                {**self.default_group, 'query': {'x': 'y'}},
            ),

            # Nested query

            (
                {'query': {'x': [{'y': 'z'}, 1, 2, 3]}},
                {**self.default_group, 'query': {'x': [{'y': 'z'}, 1, 2, 3]}},
            ),

            # Queries containing special characters

            (
                {'query': {'a.b': 'c'}},
                {**self.default_group, 'query': {'a.b': 'c'}},
            ),
            (
                {'query': {'a$b': 'c'}},
                {**self.default_group, 'query': {'a$b': 'c'}},
            ),
            (
                {'query': {'a\0b': 'c'}},
                {**self.default_group, 'query': {'a\0b': 'c'}},
            ),
        ]

    def test_duplicate_names(self):
        group1 = Group(name=random_name())
        group2 = Group(name=random_name.last)

        assert group1.name == group2.name

        group1.save()

        with pytest.raises(APIRequestError) as excinfo:
            group2.save()

        assert excinfo.value.response.json() == {
            'name': ['This field must be unique.'],
        }
