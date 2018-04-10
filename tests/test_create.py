import pytest

from perfectstorm import Agent, Group
from perfectstorm.exceptions import APIRequestError, ValidationError

from .stubs import ANY, IDENTIFIER, PLACEHOLDER


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

        actual_data = obj._data
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


class TestAgentCreation(BaseTestDocumentCreation):

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
