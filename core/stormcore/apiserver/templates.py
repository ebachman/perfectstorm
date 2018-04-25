import jinja2.sandbox

from stormcore.apiserver.models import (
    Resource, Group, user_query_filter)
from stormcore.apiserver.serializers import (
    ResourceSerializer, GroupSerializer)


def render(template, target, params):
    env = jinja2.sandbox.SandboxedEnvironment(
        extensions=['jinja2.ext.do'],
        line_statement_prefix='%',
        line_comment_prefix='##',
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template_params = {
        'groups': JinjaGroups(),
        'resources': JinjaResources(),
        'target': JinjaResources()._serialize(target),
        **params,
    }

    renderer = env.from_string(template)
    return renderer.render(template_params)


class JinjaQuerySet:

    def __init__(self, queryset, serializer_class):
        self._queryset = queryset
        self._serializer_class = serializer_class

    def _serialize(self, obj):
        serializer = self._serializer_class(obj)
        return serializer.data

    def __len__(self):
        return len(self._queryset)

    def __iter__(self):
        return (self._serialize(obj) for obj in self._queryset)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return JinjaQuerySet(
                self._queryset[index],
                self._serializer_class)
        return self._serialize(self._queryset[index])

    def __call__(self, query):
        return JinjaQuerySet(
            user_query_filter(query, self._queryset),
            self._serializer_class)


class JinjaDocumentClass(JinjaQuerySet):

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._serialize(self._queryset.lookup(key))
        return super().__getitem__(key)


class JinjaResources(JinjaDocumentClass):

    def __init__(self):
        super().__init__(Resource.objects.all(), ResourceSerializer)


class JinjaGroups(JinjaDocumentClass):

    def __init__(self):
        super().__init__(Group.objects.all(), GroupSerializer)

    def _serialize(self, obj):
        data = super()._serialize(obj)
        data['members'] = JinjaQuerySet(
            obj.members(), ResourceSerializer)
        return data
