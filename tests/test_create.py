import re

import pytest

from perfectstorm import Resource
from perfectstorm.exceptions import APIRequestError, ValidationError


class PlaceholderType:

    def __eq__(self, other):
        return False

    def __repr__(self):
        return 'PLACEHOLDER'


PLACEHOLDER = PlaceholderType()


class BaseTestDocumentCreation:

    def pytest_generate_tests(self, metafunc):
        if metafunc.function.__name__ == 'test_client_create':
            metafunc.parametrize('input_data, expected_data', self.valid_client_data)
        elif metafunc.function.__name__ == 'test_server_create':
            metafunc.parametrize('input_data, expected_data', self.valid_server_data)
        elif metafunc.function.__name__ == 'test_client_validation':
            metafunc.parametrize('input_data, expected_error', self.invalid_client_data)
        elif metafunc.function.__name__ == 'test_server_validation':
            metafunc.parametrize('input_data, expected_error', self.invalid_server_data)

    valid_data = []
    valid_client_only_data = []
    valid_server_only_data = []

    invalid_data = []
    invalid_client_only_data = []
    invalid_server_only_data = []

    @property
    def valid_client_data(self):
        return self.valid_data + self.valid_client_only_data

    @property
    def valid_server_data(self):
        return self.valid_data + self.valid_server_only_data

    @property
    def invalid_client_data(self):
        return [
            (data, client_error)
            for data, client_error, server_error in self.invalid_data
        ] + self.invalid_client_only_data

    @property
    def invalid_server_data(self):
        return [
            (data, server_error)
            for data, client_error, server_error in self.invalid_data
        ] + self.invalid_server_only_data

    def test_client_create(self, input_data, expected_data):
        obj = self.model(**input_data)
        self.check_object_before_save(obj, input_data)

        obj.save()

        self.check_object_after_save(obj, input_data, expected_data)

    def test_server_create(self, api_session, input_data, expected_data):
        response_data = api_session.post(self.model._path, json=input_data)
        self.check_response_after_save(input_data, expected_data, response_data)

    def test_client_validation(self, input_data, expected_error):
        obj = self.model(**input_data)
        self.check_object_before_save(obj, input_data)

        with pytest.raises(ValidationError) as excinfo:
            obj.save()

        self.check_client_error(obj, input_data, expected_error, excinfo)

    def test_server_validation(self, api_session, input_data, expected_error):
        with pytest.raises(APIRequestError) as excinfo:
            api_session.post(self.model._path, json=input_data)

        self.check_server_error(input_data, expected_error, excinfo)

    def check_object_before_save(self, obj, input_data):
        assert obj.id is None

    def check_object_after_save(self, obj, input_data, expected_data):
        assert obj.id is not None
        assert re.match('^[a-z]+-[0-9A-Za-z]{22}$', obj.id)

        actual_data = {
            key: getattr(obj, key)
            for key in expected_data
        }
        assert actual_data == expected_data

    def check_response_after_save(self, input_data, expected_data, response_data):
        actual_data = {
            key: response_data[key]
            for key in expected_data
        }
        assert actual_data == expected_data

    def check_client_error(self, obj, input_data, expected_error, excinfo):
        assert obj.id is None
        assert type(excinfo.value) is ValidationError
        assert str(excinfo.value) == expected_error

    def check_server_error(self, input_data, expected_error, excinfo):
        assert type(excinfo.value) is APIRequestError
        assert excinfo.value.response.status_code == 400
        assert excinfo.value.response.json() == expected_error


class BaseTestDocumentCreationWithAgent(BaseTestDocumentCreation):

    def test_client_create(self, agent, input_data, expected_data):
        self.set_owner(agent, input_data)
        self.set_owner(agent, expected_data)
        super().test_client_create(input_data, expected_data)

    def test_server_create(self, api_session, agent, input_data, expected_data):
        self.set_owner(agent, input_data)
        self.set_owner(agent, expected_data)
        super().test_server_create(api_session, input_data, expected_data)

    def test_client_validation(self, agent, input_data, expected_error):
        self.set_owner(agent, input_data)
        super().test_client_validation(input_data, expected_error)

    def test_server_validation(self, api_session, agent, input_data, expected_error):
        self.set_owner(agent, input_data)
        super().test_server_validation(api_session, input_data, expected_error)

    def set_owner(self, agent, data):
        if data.get('owner') is PLACEHOLDER:
            data['owner'] = agent.id


class TestResourceCreation(BaseTestDocumentCreationWithAgent):

    model = Resource

    default_resource = {
        'type': PLACEHOLDER,
        'owner': PLACEHOLDER,
        'names': [],
        'parent': None,
        'image': None,
        'status': 'unknown',
        'health': 'unknown',
        'snapshot': {},
    }

    valid_data = [
        (
            {'type': 'test', 'owner': PLACEHOLDER},
            {**default_resource, 'type': 'test'},
        ),
        (
            {'type': 'test', 'names': None, 'owner': PLACEHOLDER},
            {**default_resource, 'type': 'test'},
        ),
        (
            {'type': 'test', 'names': [], 'owner': PLACEHOLDER},
            {**default_resource, 'type': 'test'},
        ),
        (
            {'type': 'test', 'names': ['woot'], 'owner': PLACEHOLDER},
            {**default_resource, 'type': 'test', 'names': ['woot']},
        ),
        (
            {'type': 'test', 'names': ['woot', 'waat', 'weet'], 'owner': PLACEHOLDER},
            {**default_resource, 'type': 'test', 'names': ['woot', 'waat', 'weet']},
        ),
        (
            {**default_resource, 'type': 'test'},
            {**default_resource, 'type': 'test'},
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
    ]
