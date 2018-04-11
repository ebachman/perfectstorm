import pytest

from perfectstorm import Resource
from perfectstorm.exceptions import ObjectNotFound

from .stubs import IDENTIFIER, PLACEHOLDER, random_name
from .test_create import BaseTestDocumentCreationWithAgent


def assert_resources_count(expected_count, **kwargs):
    resource_set = Resource.objects.filter(**kwargs)
    assert len(resource_set) == expected_count


class TestCreate(BaseTestDocumentCreationWithAgent):

    model = Resource

    default_resource = {
        'id': IDENTIFIER,
        'type': PLACEHOLDER,
        'owner': PLACEHOLDER,
        'names': [],
        'parent': None,
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
                {'type': 'test', 'owner': PLACEHOLDER, 'names': [random_name()]},
                {**self.default_resource, 'type': 'test', 'names': [random_name.last]},
            ),
            (
                {'type': 'test', 'owner': PLACEHOLDER, 'names': [
                    random_name(1), random_name(2), random_name(3),
                 ]},
                {**self.default_resource, 'type': 'test', 'names': [
                    random_name.recall(1), random_name.recall(2), random_name.recall(3),
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
            'type: field cannot be None',
            {'owner': ['This field is required.'],
             'type': ['This field is required.']},
        ),
        (
            {'type': 'test'},
            'owner: field cannot be None',
            {'owner': ['This field is required.']},
        ),
        (
            {'owner': PLACEHOLDER},
            'type: field cannot be None',
            {'type': ['This field is required.']},
        ),

        # Null fields

        (
            {'type': None, 'names': ['namez'], 'owner': PLACEHOLDER},
            'type: field cannot be None',
            {'type': ['This field may not be null.']},
        ),
        (
            {'type': 'typez', 'names': [None], 'owner': PLACEHOLDER},
            'names.[]: field cannot be None',
            {'names': ['This field may not be null.']},
        ),

        # Empty fields

        (
            {'type': '', 'names': ['namez'], 'owner': PLACEHOLDER},
            'type: field cannot be blank',
            {'type': ['This field may not be blank.']},
        ),
        (
            {'type': 'typez', 'names': [''], 'owner': PLACEHOLDER},
            'names: field cannot be blank',
            {'names': ['This field may not be blank.']},
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

    def test_update_type(self, resource):
        assert resource.type == 'test'
        assert_resources_count(1, type='test')
        assert_resources_count(0, type='dummy')

        resource.type = 'dummy'
        resource.save()

        assert resource.type == 'dummy'
        assert_resources_count(0, type='test')
        assert_resources_count(1, type='dummy')

    def test_update_names(self, resource):
        assert resource.names == ['abc', 'def']
        assert_resources_count(1, names='abc')
        assert_resources_count(1, names='def')
        assert_resources_count(0, names='ghi')

        resource.names = ['ghi']
        resource.save()

        assert resource.names == ['ghi']
        assert_resources_count(0, names='abc')
        assert_resources_count(0, names='def')
        assert_resources_count(1, names='ghi')


class TestRetrieval:

    @pytest.fixture()
    def resources(self, agent):
        resources = []

        for type_label in 'abc':
            for num in '123':
                resource = Resource(
                    id='id-{}-{}'.format(type_label, num),
                    type='type-{}'.format(type_label),
                    names=[
                        'name-{}-{}-1'.format(type_label, num),
                        'name-{}-{}-2'.format(type_label, num),
                        'name-{}-{}-3'.format(type_label, num),
                        'common-name',
                    ],
                    owner=agent.id,
                )
                resource.save()
                assert resource.id is not None

                resources.append(resource)

        return resources

    def test_retrieve_by_id(self, resources):
        for res in resources:
            Resource.objects.get(res.id)

    def test_retrieve_by_invalid_id(self, resources):
        with pytest.raises(ObjectNotFound):
            Resource.objects.get('uneistent')

    def test_retrieve_by_name(self, resources):
        for res in resources:
            for name in res.names:
                if name == 'common-name':
                    continue
                Resource.objects.get(name)

    def test_retrieve_by_invalid_name(self, resources):
        with pytest.raises(ObjectNotFound):
            Resource.objects.get('unexistent')

    def test_retrieve_by_common_name(self, resources):
        with pytest.raises(ObjectNotFound):
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
            lambda res: res.image is not None and res.image.startswith('library/nginx:1.13'),
        ),
        (
            {'$or': [{'type': 'alpha'}, {'type': 'beta'}]},
            lambda res: res.type in ('alpha', 'beta'),
        ),
        (
            {'$and': [{'type': 'alpha'}, {'image': 'library/mongo:latest'}]},
            lambda res: res.type == 'alpha' and res.image == 'library/mongo:latest',
        ),
        (
            {'$and': [{'type': 'alpha'}, {'type': 'beta'}]},
            lambda res: False,
        ),
    ])
    def test_filters(self, clean_resources, random_resources, query, filterfunc):
        matched_resources = Resource.objects.filter(query)
        expected_resources = list(filter(filterfunc, random_resources))

        # Check whether the number of resources returned is correct
        assert len(matched_resources) == len(expected_resources)

        # Check whether the IDs returned are correct (i.e. there are no duplicates)
        matched_resource_ids = {res.id for res in matched_resources}
        expected_resource_ids = {res.id for res in expected_resources}
        assert matched_resource_ids == expected_resource_ids

        # Check whether the filter returned resources that correctly
        # satisfy the conditions
        for res in matched_resources:
            assert filterfunc(res)
