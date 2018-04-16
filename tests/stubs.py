import itertools
import random
import re


class AnyType:

    def __eq__(self, other):
        return True

    def __repr__(self):
        return 'ANY'


class PlaceholderType:

    def __eq__(self, other):
        return False

    def __repr__(self):
        return 'PLACEHOLDER'


class RegexMatcher:

    def __init__(self, regex):
        self.regex = re.compile(regex)

    def __eq__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        return self.regex.match(other) is not None

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.regex.pattern)


ANY = AnyType()
PLACEHOLDER = PlaceholderType()
IDENTIFIER = RegexMatcher('^[a-z]{3}-[0-9A-Za-z]{22}$')


class RandomNameGenerator:

    _adjectives = [
        'absent',
        'ambiguous',
        'apathetic',
        'barbarous',
        'chunky',
        'dizzy',
        'fortunate',
        'funny',
        'giant',
        'historical',
        'languid',
        'righteous',
        'shaggy',
        'symptomatic',
        'thoughtful',
        'uppity',
    ]

    _names = [
        'pythagoras',
        'ramanujan',
        'riemann',
        'rutherford',
        'ampere',
        'archimedes',
        'fermi',
        'fibonacci',
        'galilei',
        'gauss',
        'hilbert',
        'lebesgue',
        'newton',
        'pascal',
        'popper',
        'tesla',
    ]

    def __init__(self):
        sequence = [
            '-'.join(item)
            for item in itertools.product(
                self._adjectives,
                self._adjectives,
                self._names)
        ]
        random.shuffle(sequence)
        self._it = iter(sequence)
        self._markers = {}

    def __call__(self, marker=None):
        name = next(self._it)
        self._last = name
        self._markers[marker] = name
        return name

    @property
    def last(self):
        return self._last

    def recall(self, marker=None):
        return self._markers[marker]


random_name = RandomNameGenerator()
