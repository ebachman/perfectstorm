import pytest

from perfectstorm import Resource


@pytest.mark.parametrize('filters, expected_query', [
    (
        [{}],
        {},
    ),
    (
        [{'x': 1, 'y': 2}],
        {'x': 1, 'y': 2},
    ),
    (
        [{'x': 1, 'y': 2}, {'a': 3, 'b': 4}],
        {'x': 1, 'y': 2, 'a': 3, 'b': 4},
    ),
    (
        [{'a': 1}, {'b': 2}, {'c': 3}, {'d': 4}],
        {'a': 1, 'b': 2, 'c': 3, 'd': 4},
    ),
    (
        [{'x': 1}, {'x': 2}],
        {'$and': [{'x': 1}, {'x': 2}]},
    ),
    (
        [{'x': 1}, {'x': 2}, {'y': 3}],
        {'$and': [{'x': 1}, {'x': 2}, {'y': 3}]},
    ),
    (
        [{'$or': [{'x': 1}, {'y': 2}]}, {'z': 3}],
        {'$and': [{'$or': [{'x': 1}, {'y': 2}]}, {'z': 3}]},
    ),
    (
        [{'$and': [{'x': 1}, {'y': 2}]}, {'z': 3}],
        {'$and': [{'x': 1}, {'y': 2}, {'z': 3}]},
    ),
])
def test_query(filters, expected_query):
    queryset = Resource.objects.all()
    for q in filters:
        queryset = queryset.filter(**q)

    assert queryset._query == expected_query
