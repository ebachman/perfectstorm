import re
from uuid import UUID, uuid4

import pytest


@pytest.fixture(scope='session')
def models():
    try:
        from stormcore.apiserver import models
    except ImportError:
        pytest.skip('cannot import stormcore')
    return models


def base62_to_int(s):
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    return sum(
        62 ** i * alphabet.index(c)
        for i, c in enumerate(reversed(s))
    )


@pytest.mark.parametrize('hex_uuid, b62_uuid', [
    ('00000000-0000-0000-0000-000000000000', '0000000000000000000000'),
    ('00000000-0000-0000-0000-000000000001', '0000000000000000000001'),
    ('00000000-0000-0000-0000-000000000002', '0000000000000000000002'),
    ('00000000-0000-0000-0000-00000000000f', '000000000000000000000F'),
    ('10000000-0000-0000-0000-000000000000', '0UBsO4td5jEbl6wfnwZr6G'),
    ('20000000-0000-0000-0000-000000000000', '0yNkm9nGBSTDWDtLbt9iCW'),
    ('f0000000-0000-0000-0000-000000000000', '7Is9pBSSNwX8OgC75AfqVs'),
    ('ffffffff-ffff-ffff-ffff-ffffffffffff', '7n42DGM5Tflk9n8mt7Fhc7'),
    ('21f165ce-f08b-4c6e-3928-3cc68ff8baab', '123456ABCDEFGHabcdefgh'),
    ('01234567-abcd-bcde-cdef-123abc123abc', '0296tivvN5MrvPXxjADb1I'),
])
def test_base62_encoding(models, hex_uuid, b62_uuid):
    uuid = UUID(hex_uuid)
    assert models.b62uuid_encode(uuid) == b62_uuid
    assert uuid.int == base62_to_int(b62_uuid)


def test_base62_encoding_random(models):
    for i in range(256):
        uuid = uuid4()
        b62uuid = models.b62uuid_encode(uuid)
        assert uuid.int == base62_to_int(b62uuid)


def test_base62_uuid_generation(models):
    for i in range(256):
        b62uuid = models.b62uuid_new(method=uuid4)
        assert re.match('^[0-9a-zA-Z]{22}$', b62uuid)


def test_base62_uuid_generation_with_prefix(models):
    for i in range(256):
        b62uuid = models.b62uuid_new(prefix='prefix-', method=uuid4)
        assert re.match('^prefix-[0-9a-zA-Z]{22}$', b62uuid)
