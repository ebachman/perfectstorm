import abc
import json
import threading

from ..exceptions import APINotFoundError, ObjectNotFound, MultipleObjectsReturned
from .fields import StringField
from .session import current_session


def json_compact(*args, **kwargs):
    kwargs.setdefault('separators', (',', ':'))
    return json.dumps(*args, **kwargs)


def combine_queries(query1, query2):
    if not query1:
        return query2
    if not query2:
        return query1

    all_keys = set(query1) | set(query2)
    common_keys = set(query1) & set(query2)
    uses_operators = any(key.startswith('$') for key in all_keys)

    if not common_keys and not uses_operators:
        # Merging: {'x': 1, 'y': 2} with {'a': 3, 'b': 4}
        # Result: {'x': 1, 'y': 2, 'a': 3, 'b': 4}
        return {**query1, **query2}

    query1_and = (list(query1) == ['$and'])
    query2_and = (list(query2) == ['$and'])

    if query1_and and query2_and:
        # Merging: {'$and': [...]} with {'$and': [...]}
        # Result: {'$and': [...]}
        return {'$and': query1['$and'] + query2['$and']}

    if query1_and:
        # Merging: {'$and': [...]} with {'x': 1, 'y': 2}
        # Result: {'$and': [..., {'x': 1, 'y': 2}]}
        return {'$and': query1['$and'] + [query2]}

    if query2_and:
        # Merging: {'x': 1, 'y': 2} with {'$and': [...]}
        # Result: {'$and': [{'x': 1, 'y': 2}, ...]}
        return {'$and': [query1] + query2['$and']}

    # Merging: {'x': 1} with {'x': 2}
    # Merging: {'$or': [...]} with {'$or': [...]}
    # Result: {'$and': [{'$or': [...]}, {'$or': [...]}]}
    return {'$and': [query1, query2]}


class AbstractCollection(metaclass=abc.ABCMeta):

    def __init__(self, model):
        self.model = model

    @abc.abstractmethod
    def all(self):
        raise NotImplementedError

    @abc.abstractmethod
    def filter(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __len__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __getitem__(self, index):
        raise NotImplementedError

    def __repr__(self):
        return '<{}: {!r}>' % (self.__class__.__name__, list(self))


class Collection(AbstractCollection):

    def __init__(self, model, query=None, session=None):
        super().__init__(model=model)
        if query is None:
            query = {}
        self._query = query
        if session is None:
            session = current_session()
        self._session = session
        self._elems = None
        self._lock = threading.RLock()

    def _replace(self, **kwargs):
        kwargs.setdefault('model', self.model)
        kwargs.setdefault('query', self._query)
        kwargs.setdefault('session', self._session)
        return self.__class__(**kwargs)

    @property
    def base_url(self):
        return self._session.api_root / self.model._path

    @property
    def url(self):
        if self._query:
            params = {'q': json_compact(self._query)}
        else:
            params = {}
        return self.base_url.params(params)

    def all(self):
        return self._replace()

    def filter(self, **kwargs):
        query = combine_queries(self._query, kwargs)
        return self._replace(query=query)

    def get(self, **kwargs):
        if kwargs:
            it = iter(self.filter(kwargs))
        else:
            it = iter(self)

        try:
            obj = next(it)
        except StopIteration:
            raise ObjectNotFound('%s matching query does not exist' % self.model.__name__)

        try:
            next(it)
        except StopIteration:
            pass
        else:
            raise MultipleObjectsReturned('Multiple objects returned instead of 1')

        return obj

    def __iter__(self):
        return iter(self._retrieve())

    def __len__(self):
        return len(self._retrieve())

    def __getitem__(self, index):
        return self._retrieve()[index]

    def _retrieve(self):
        if self._elems is not None:
            return self._elems

        with self._lock:
            if self._elems is not None:
                return self._elems

            documents = self._session.get(self.url)
            self._elems = [self.model(doc, session=self._session) for doc in documents]

        return self._elems


class EmptyCollection(AbstractCollection):

    def all(self):
        return self

    def filter(self, **kwargs):
        return self

    def get(self, **kwargs):
        raise ObjectNotFound

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0

    def __getitem__(self, index):
        if isinstance(index, slice):
            return []
        raise IndexError(index)


class Manager:

    def __init__(self, model, session=None):
        self.model = model
        self._session = session

    def _replace(self, **kwargs):
        kwargs.setdefault('model', self.model)
        kwargs.setdefault('session', self._session)
        return self.__class__(**kwargs)

    @property
    def url(self):
        session = self._session if self._session is not None else current_session()
        return session.api_root / self.model._path

    def none(self):
        return EmptyCollection(model=self.model)

    def all(self):
        return Collection(model=self.model, session=self._session)

    def filter(self, **kwargs):
        return Collection(
            model=self.model,
            query=kwargs,
            session=self._session)

    def get(self, *args, **kwargs):
        """
        get(identifier)
        Retrieve an object with the given identifier

        get(key1='value', key2='value', ...)
        Retrieve an object matching the given query
        """
        if args:
            if len(args) > 1:
                raise TypeError(
                    'get() takes from 0 to 1 positional '
                    'argument but {} were given'
                    .format(len(args)))
            if kwargs:
                raise TypeError(
                    'get() does not accept positional arguments '
                    'together with keyword arguments')

            identifier, = args
            obj = self.model(id=identifier)
            obj.reload()

            return obj

        return self.filter(*args, **kwargs).get()


class ModelMeta(type):

    def __new__(mcls, name, bases, attrs, **kwargs):
        for attr in ('_fields', '_primary_keys'):
            if attr in attrs:
                raise TypeError('Reserved attribute: %r' % attr)
            value = []
            for base in reversed(bases):
                value.extend(getattr(base, attr, []))
            attrs[attr] = value

        cls = super().__new__(mcls, name, bases, attrs, **kwargs)
        cls.objects = Manager(cls)

        return cls


class Model(metaclass=ModelMeta):

    id = StringField(null=True)

    def __init__(self, data=None, session=None, **kwargs):
        super().__init__()

        non_field_kwargs = [key for key in kwargs if key not in self._fields]
        if non_field_kwargs:
            raise TypeError('__init__() got an unexpected keyword argument {!r}'.format(non_field_kwargs))

        if session is None:
            session = current_session()
        self._session = session

        self._data = {}

        if data is None:
            data = {}
        if kwargs:
            data = dict(data, **kwargs)

        for key, value in data.items():
            if key in self._fields:
                setattr(self, key, value)

    @property
    def url(self):
        if self.id is None:
            raise AttributeError('No ID has been set')
        return self.objects.url / self.id

    def reload(self, session=None):
        """Fetch the data from the API server for this object."""
        if session is None:
            session = self._session
        try:
            response_data = session.get(self.url)
        except APINotFoundError as exc:
            raise ObjectNotFound(self.id)
        self._data = response_data

    def save(self, validate=True, session=None):
        """
        Store the object on the API server. This will either create a new
        entity or update an existing one, depending on whether this object has
        an ID or not.
        """
        if validate:
            self.validate()

        if session is None:
            session = self._session

        if self.id is not None:
            # If an ID is defined, try to update
            try:
                self._update(session)
            except ObjectNotFound:
                pass
            else:
                return

        # Either an ID is not defined, or the update returned 404
        self._create(session)

    def _create(self, session):
        response_data = session.post(self.objects.url, json=self._data)
        self._data = response_data

    def _update(self, session):
        try:
            response_data = session.put(self.url, json=self._data)
        except APINotFoundError as exc:
            raise ObjectNotFound(self.id)
        self._data = response_data

    def delete(self, session=None):
        """Delete this object from the API server."""
        if session is None:
            session = self._session

        try:
            session.delete(self.url)
        except APINotFoundError as exc:
            raise ObjectNotFound(self.id)

    def validate(self, skip_fields=None):
        cls = self.__class__
        for name in self._fields:
            if skip_fields is not None and name in skip_fields:
                continue
            field = getattr(cls, name)
            if not field.read_only:
                value = getattr(self, name)
                field.validate(value)

    def __str__(self):
        return str(self.id)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, str(self))
