import pytest

from stormlib import Resource
from stormlib.exceptions import StormObjectNotFound

from .create import BaseTestCreateWithAgent
from .samples import create_agent, delete_on_exit
from .stubs import IDENTIFIER, PLACEHOLDER, random_name


def assert_resources_count(expected_count, **kwargs):
    resource_set = Resource.objects.filter(**kwargs)
    assert len(resource_set) == expected_count


def exclude_foreign_resources(returned_resource_set, expected_resource_set):
    """
    Return a subset of `returned_resource_set` that contains only resources
    created by the test suite.

    Resources are filtering by comparing them with `expected_resource_set`:
    if the owner matches, then they are considered as being created by the
    test suite.
    """
    expected_owners = {res.owner for res in expected_resource_set}
    return [
        res for res in returned_resource_set
        if res.owner in expected_owners
    ]


def assert_resources_equal(actual_resource_set, expected_resource_set):
    actual_resource_set = exclude_foreign_resources(
        actual_resource_set, expected_resource_set)

    actual_resource_map = {res.id: res for res in actual_resource_set}
    expected_resource_map = {res.id: res for res in expected_resource_set}

    # Check whether the number of resources returned is correct
    assert len(actual_resource_set) == len(expected_resource_set)

    # Check whether the IDs returned are correct (i.e. there are no duplicates)
    assert len(actual_resource_map) == len(expected_resource_map)
    assert actual_resource_map.keys() == expected_resource_map.keys()

    # Check all the fields of the resources
    for res_id in expected_resource_map:
        actual_resource = actual_resource_map[res_id]
        expected_resource = expected_resource_map[res_id]
        assert actual_resource._data == expected_resource._data


class TestCreate(BaseTestCreateWithAgent):

    model = Resource

    default_resource = {
        'id': IDENTIFIER,
        'type': PLACEHOLDER,
        'owner': PLACEHOLDER,
        'names': [],
        'parent': None,
        'cluster': None,
        'host': None,
        'image': None,
        'status': 'unknown',
        'health': 'unknown',
        'snapshot': {},
    }

    @property
    def valid_data(self):
        # This is a property so that random_name() can return a new value
        # every time this attribute is accessed.
        return [
            (
                {'type': 'test', 'owner': PLACEHOLDER},
                {**self.default_resource, 'type': 'test'},
            ),
            (
                {'type': 'test', 'owner': PLACEHOLDER, 'names': []},
                {**self.default_resource, 'type': 'test'},
            ),
            (
                {
                    'type': 'test',
                    'owner': PLACEHOLDER,
                    'names': [random_name()],
                },
                {
                    **self.default_resource,
                    'type': 'test',
                    'names': [random_name.last],
                },
            ),
            (
                {'type': 'test', 'owner': PLACEHOLDER, 'names': [
                    random_name(1),
                    random_name(2),
                    random_name(3),
                ]},
                {**self.default_resource, 'type': 'test', 'names': [
                    random_name.recall(1),
                    random_name.recall(2),
                    random_name.recall(3),
                ]},
            ),
            (
                {**self.default_resource, 'id': None, 'type': 'test'},
                {**self.default_resource, 'type': 'test'},
            ),
        ]

    invalid_data = [
        # Missing required fields

        (
            {},
            'type: Field cannot be None',
            {'owner': ['This field is required.'],
             'type': ['This field is required.']},
        ),
        (
            {'type': 'test'},
            'owner: Field cannot be None',
            {'owner': ['This field is required.']},
        ),
        (
            {'owner': PLACEHOLDER},
            'type: Field cannot be None',
            {'type': ['This field is required.']},
        ),

        # Null fields

        (
            {'type': None, 'names': ['namez'], 'owner': PLACEHOLDER},
            'type: Field cannot be None',
            {'type': ['This field may not be null.']},
        ),
        (
            {'type': 'typez', 'names': [None], 'owner': PLACEHOLDER},
            'names.[]: Field cannot be None',
            {'names': {'0': ['This field may not be null.']}},
        ),

        # Empty fields

        (
            {'type': '', 'names': ['namez'], 'owner': PLACEHOLDER},
            'type: Field cannot be blank',
            {'type': ['This field may not be blank.']},
        ),
        (
            {'type': 'typez', 'names': [''], 'owner': PLACEHOLDER},
            'names.[]: Field cannot be blank',
            {'names': {'0': ['This field may not be blank.']}},
        ),
    ]

    invalid_server_only_data = [
        # Invalid owner

        (
            {'type': 'test', 'owner': 'fake'},
            {'owner': ['Document with id=fake does not exist.']},
        ),

        # Wrong types

        (
            {'type': 'test', 'owner': PLACEHOLDER, 'names': None},
            {'names': ['This field may not be null.']},
        ),
    ]


class TestUpdate:

    @pytest.fixture()
    def resource(self, agent):
        resource = Resource(
            type='test',
            names=['abc', 'def'],
            owner=agent.id,
        )
        resource.save()
        assert resource.id is not None
        return resource

    def test_update_type(self, agent, resource):
        assert resource.type == 'test'
        assert_resources_count(1, owner=agent.id, type='test')
        assert_resources_count(0, owner=agent.id, type='dummy')

        resource.type = 'dummy'
        resource.save()

        assert resource.type == 'dummy'
        assert_resources_count(0, owner=agent.id, type='test')
        assert_resources_count(1, owner=agent.id, type='dummy')

    def test_update_names(self, agent, resource):
        assert resource.names == ['abc', 'def']
        assert_resources_count(1, owner=agent.id, names='abc')
        assert_resources_count(1, owner=agent.id, names='def')
        assert_resources_count(0, owner=agent.id, names='ghi')

        resource.names = ['ghi']
        resource.save()

        assert resource.names == ['ghi']
        assert_resources_count(0, owner=agent.id, names='abc')
        assert_resources_count(0, owner=agent.id, names='def')
        assert_resources_count(1, owner=agent.id, names='ghi')


class TestRetrieval:

    @pytest.fixture(scope='module')
    def resources(self):
        resources = []

        agent = create_agent()

        for type_label in 'xyz':
            for num in 'abc':
                resource = Resource(
                    id='id-{}-{}'.format(type_label, num),
                    type='type-{}'.format(type_label),
                    names=[
                        'name-{}-{}.1'.format(type_label, num),
                        'name-{}-{}.2'.format(type_label, num),
                        'name-{}-{}.3'.format(type_label, num),
                        'common-name',
                    ],
                    owner=agent.id,
                )
                resource.save()
                assert resource.id is not None

                resources.append(resource)

        with delete_on_exit(agent):
            with delete_on_exit(resources):
                yield resources

    def test_retrieve_by_id(self, resources):
        for res in resources:
            Resource.objects.get(res.id)

    def test_retrieve_by_invalid_id(self, resources):
        with pytest.raises(StormObjectNotFound):
            Resource.objects.get('uneistent')

    def test_retrieve_by_name(self, resources):
        for res in resources:
            for name in res.names:
                if name == 'common-name':
                    continue
                Resource.objects.get(name)

    def test_retrieve_by_invalid_name(self, resources):
        with pytest.raises(StormObjectNotFound):
            Resource.objects.get('unexistent')

    def test_retrieve_by_common_name(self, resources):
        with pytest.raises(StormObjectNotFound):
            Resource.objects.get('common-name')


class TestFiltering:

    @pytest.mark.parametrize('query, filterfunc', [
        (
            {},
            lambda res: True
        ),
        (
            {'type': 'alpha'},
            lambda res: res.type == 'alpha',
        ),
        (
            {'type': {'$ne': 'alpha'}},
            lambda res: res.type != 'alpha',
        ),
        (
            {'image': None},
            lambda res: res.image is None,
        ),
        (
            {'image': {'$regex': '^library/nginx:1.13'}},
            lambda res: (
                res.image is not None and
                res.image.startswith('library/nginx:1.13')),
        ),
        (
            {'$or': [{'type': 'alpha'}, {'type': 'beta'}]},
            lambda res: res.type in ('alpha', 'beta'),
        ),
        (
            {'$and': [{'type': 'alpha'}, {'image': 'library/mongo:latest'}]},
            lambda res: (
                res.type == 'alpha' and
                res.image == 'library/mongo:latest'),
        ),
        (
            {'$and': [{'type': 'alpha'}, {'type': 'beta'}]},
            lambda res: False,
        ),
    ])
    def test_filters(self, random_resources, query, filterfunc):
        matched_resources = Resource.objects.filter(**query)
        expected_resources = list(filter(filterfunc, random_resources))
        assert_resources_equal(matched_resources, expected_resources)
