import pytest

from stormlib import Group
from stormlib.exceptions import StormAPIError

from .create import BaseTestCreate
from .stubs import IDENTIFIER, random_name
from .test_resources import assert_resources_equal


class TestCreate(BaseTestCreate):

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

    invalid_data = [
        # Wrong types

        (
            {'query': 'hello'},
            "query: Expected a dict, got 'hello'",
            {'query': ['Expected a JSON object.']},
        ),

        (
            {'include': {'x': 'y'}},
            "include: Expected a list or tuple, got {'x': 'y'}",
            {'include': ['Expected a list of items but got type "dict".']},
        ),
    ]

    def test_duplicate_names(self):
        group1 = Group(name=random_name())
        group2 = Group(name=random_name.last)

        assert group1.name == group2.name

        group1.save()

        with pytest.raises(StormAPIError) as excinfo:
            group2.save()

        assert excinfo.value.response.json() == {
            'name': ['This field must be unique.'],
        }


@pytest.mark.parametrize('query, filterfunc', [
    (
        {},
        lambda res: False,
    ),
    (
        {'type': 'alpha'},
        lambda res: res.type == 'alpha',
    ),
    (
        {'status': 'running', 'health': 'healthy'},
        lambda res: res.status == 'running' and res.health == 'healthy',
    ),
    (
        {'$or': [
            {'status': {'$ne': 'running'}},
            {'health': {'$ne': 'healthy'}},
        ]},
        lambda res: res.status != 'running' or res.health != 'healthy',
    ),
    (
        {'image': {'$regex': 'nginx'}},
        lambda res: res.image is not None and 'nginx' in res.image,
    ),

    # Test queries with special characters

    (
        {'a.b': 'c'},
        lambda res: False,
    ),
    (
        {'a$b': 'c'},
        lambda res: False,
    ),
    (
        {'a\0b': 'c'},
        lambda res: False,
    ),
])
class TestMembers:

    def create_group(self, **kwargs):
        group = Group(**kwargs)
        group.save()
        return group

    def test_query_only(self, random_resources, query, filterfunc):
        group = self.create_group(query=query)

        matched_resources = group.members()
        expected_resources = list(filter(filterfunc, random_resources))

        assert_resources_equal(matched_resources, expected_resources)

    def test_include(self, random_resources, query, filterfunc):
        expected_resources = list(filter(filterfunc, random_resources))
        unmatched_resources = [
            res for res in random_resources if res not in expected_resources]
        included_resources = unmatched_resources[:10]
        expected_resources.extend(included_resources)

        include = [res.id for res in included_resources]
        group = self.create_group(query=query, include=include)

        matched_resources = group.members()
        assert_resources_equal(matched_resources, expected_resources)

    def test_exclude(self, random_resources, query, filterfunc):
        expected_resources = list(filter(filterfunc, random_resources))
        excluded_resources = expected_resources[-10:]
        del expected_resources[-10:]

        exclude = [res.id for res in excluded_resources]
        group = self.create_group(query=query, exclude=exclude)

        matched_resources = group.members()
        assert_resources_equal(matched_resources, expected_resources)

    def test_include_exclude(self, random_resources, query, filterfunc):
        expected_resources = list(filter(filterfunc, random_resources))
        unmatched_resources = [
            res for res in random_resources if res not in expected_resources]

        excluded_resources = expected_resources[-10:]
        del expected_resources[-10:]

        included_resources = unmatched_resources[:10]
        expected_resources.extend(included_resources)

        include = [res.id for res in included_resources]
        exclude = [res.id for res in excluded_resources]
        group = self.create_group(
            query=query, include=include, exclude=exclude)

        matched_resources = group.members()
        assert_resources_equal(matched_resources, expected_resources)
