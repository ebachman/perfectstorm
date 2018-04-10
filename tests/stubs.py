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


ANY = AnyType()
PLACEHOLDER = PlaceholderType()
IDENTIFIER = RegexMatcher('^[a-z]+-[0-9A-Za-z]{22}$')
