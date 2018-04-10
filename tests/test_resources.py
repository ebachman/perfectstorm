import pytest

from perfectstorm import Resource
from perfectstorm.exceptions import MultipleObjectsReturned, ObjectNotFound


def assert_resources_count(expected_count, **kwargs):
    resource_set = Resource.objects.filter(**kwargs)
    assert len(resource_set) == expected_count


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
