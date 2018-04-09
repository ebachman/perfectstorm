import re

import pytest

from perfectstorm import Resource
from perfectstorm.exceptions import (
    APIRequestError,
    MultipleObjectsReturned,
    ObjectNotFound,
    ValidationError,
)


def assert_resource_matches(resource, expected_data):
    actual_data = {
        key: getattr(resource, key)
        for key in expected_data
    }
    assert actual_data == expected_data


def assert_resources_count(expected_count, **kwargs):
    resource_set = Resource.objects.filter(**kwargs)
    assert len(resource_set) == expected_count


@pytest.mark.parametrize('data', [
    dict(type='test'),
    dict(type='test', names=['test']),
    dict(type='test', names=['test1', 'test2', 'test3']),
])
class TestCreation:

    def test_create(self, agent, data):
        data['owner'] = agent.id
        resource = Resource(**data)
        assert resource.id is None

        resource.save()

        assert resource.id is not None
        assert re.match('^res-[0-9A-Za-z]{22}$', resource.id)
        assert_resource_matches(resource, data)

    def test_create_with_id(self, agent, data):
        resource_id = 'dummy-resource-id'

        assert_resources_count(0, id=resource_id)

        data['id'] = resource_id
        data['owner'] = agent.id

        resource = Resource(**data)
        resource.save()
        assert_resource_matches(resource, data)

        assert_resources_count(1, id=resource_id)


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
            Resource.objects.get(id=res.id)

    def test_retrieve_by_invalid_id(self, resources):
        with pytest.raises(ObjectNotFound):
            Resource.objects.get(id='unexistent')

    def test_retrieve_by_name(self, resources):
        for res in resources:
            for name in res.names:
                if name == 'common-name':
                    continue
                Resource.objects.get(names=name)

    def test_retrieve_by_invalid_name(self, resources):
        with pytest.raises(ObjectNotFound):
            Resource.objects.get(names='unexistent')

    def test_retrieve_by_common_name(self, resources):
        with pytest.raises(MultipleObjectsReturned):
            Resource.objects.get(names='common-name')


class TestClientValidation:

    def test_invalid_keywords(self):
        with pytest.raises(TypeError) as excinfo:
            Resource(xyz='test')

        assert str(excinfo.value) == "Keys do not map to fields: ['xyz']"

    @pytest.mark.parametrize('resource, field', [
        (Resource(), 'type'),
        (Resource(type=None), 'type'),

        (Resource(type='x'), 'owner'),
        (Resource(type='x', owner=None), 'owner'),
    ])
    def test_missing_required_field(self, resource, field):
        with pytest.raises(ValidationError) as excinfo:
            resource.validate()

        excmsg = field + ': field cannot be None'
        assert str(excinfo.value) == excmsg

    @pytest.mark.parametrize('resource, field', [
        (Resource(type='', owner='y', names=['z']), 'type'),
        (Resource(type='x', owner='', names=['z']), 'owner'),
        (Resource(type='x', owner='y', names=['']), 'names'),
    ])
    def test_empty_required_field(self, resource, field):
        with pytest.raises(ValidationError) as excinfo:
            resource.validate()

        excmsg = field + ': field cannot be empty'
        assert str(excinfo.value) == excmsg


class TestServerValidation:

    def test_invalid_keywords(self, api_session, agent):
        data = {
            'type': 'test',
            'owner': agent.id,
            'xyz': 123,
        }
        response_data = api_session.post('/v1/resources', json=data)

        assert response_data['type'] == 'test'
        assert response_data['owner'] == agent.id
        assert 'xyz' not in response_data

    @pytest.mark.parametrize('data, fields', [
        (dict(), ['type', 'owner']),
        (dict(type='x'), ['owner']),
        (dict(owner='y'), ['type']),
    ])
    def test_missing_required_field(self, api_session, data, fields):
        with pytest.raises(APIRequestError) as excinfo:
            api_session.post('/v1/resources', json=data)

        assert excinfo.value.response.status_code == 400

        error_details = excinfo.value.response.json()
        for field in fields:
            assert error_details[field] == ['This field is required.']

    @pytest.mark.parametrize('data, fields', [
        (dict(type=None, owner=None), ['type', 'owner']),
        (dict(type='x', owner=None), ['owner']),
        (dict(type=None, owner='y'), ['type']),
    ])
    def test_null_required_field(self, api_session, data, fields):
        with pytest.raises(APIRequestError) as excinfo:
            api_session.post('/v1/resources', json=data)

        assert excinfo.value.response.status_code == 400

        error_details = excinfo.value.response.json()
        for field in fields:
            assert error_details[field] == ['This field may not be null.']

    @pytest.mark.parametrize('data, field', [
        (dict(type='', owner='y', names=['z']), 'type'),
        (dict(type='x', owner='', names=['z']), 'owner'),
        (dict(type='x', owner='y', names=['']), 'names'),
    ])
    def test_empty_required_field(self, api_session, data, field):
        with pytest.raises(APIRequestError) as excinfo:
            api_session.post('/v1/resources', json=data)

        assert excinfo.value.response.status_code == 400

        error_details = excinfo.value.response.json()
        assert error_details[field] == ['This field may not be blank.']

    def test_invalid_owner(self):
        resource = Resource(
            type='test',
            owner='fake',
        )

        with pytest.raises(APIRequestError) as excinfo:
            resource.save()

        assert excinfo.value.response.status_code == 400

        error_details = excinfo.value.response.json()
        assert error_details['owner'] == [
            'Document with id=fake does not exist.',
        ]
