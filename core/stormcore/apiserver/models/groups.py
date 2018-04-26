import copy

from mongoengine import (
    EmbeddedDocument,
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    IntField,
    ListField,
    PULL,
    StringField,
    ValidationError,
)

from stormcore.apiserver.models.base import (
    StormDocument, NameMixin, EscapedDictField, StormReferenceField,
    prepare_user_query)
from stormcore.apiserver.models.resources import Resource


class Service(NameMixin, EmbeddedDocument):

    PROTOCOL_CHOICES = (
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
    )

    protocol = StringField(choices=PROTOCOL_CHOICES, required=True)
    port = IntField(required=True)

    def to_reference(self):
        return ServiceReference(group=self._instance, service_name=self.name)

    def __str__(self):
        return '{}[{}]'.format(self._instance, self.name)


class Group(NameMixin, StormDocument):

    services = EmbeddedDocumentListField(Service)

    query = EscapedDictField(required=True)
    include = ListField(StormReferenceField(
        Resource, reverse_delete_rule=PULL))
    exclude = ListField(StormReferenceField(
        Resource, reverse_delete_rule=PULL))

    meta = {
        'id_prefix': 'grp-',
    }

    def members(self, filter=None):
        query = copy.deepcopy(self.query)
        prepare_user_query(Resource, query)

        if self.include:
            cond = {'_id': {'$in': self.include}}

            if query:
                query = {'$or': [query, cond]}
            else:
                query = cond

        if self.exclude:
            cond = {'_id': {'$nin': self.exclude}}

            if query:
                query = {'$and': [query, cond]}
            else:
                query = cond

        if query and filter:
            query = {'$and': [query, filter]}

        if query:
            return Resource.objects(__raw__=query)
        else:
            return Resource.objects.none()


class ServiceReference(EmbeddedDocument):

    group = StormReferenceField(Group, required=True, reverse_delete_rule=0)
    service_name = StringField(min_length=1, required=True)

    @property
    def service(self):
        return self.group.services.get(name=self.service_name)

    def clean(self):
        available_service_names = [
            service.name for service in self.group.services]
        if self.service_name not in available_service_names:
            raise ValidationError(
                'Service {} is not provided by group {}'.format(
                    self.service_name, self.group.name))

    def __str__(self):
        return str(self.service)


class ComponentLink(EmbeddedDocument):

    from_component = StormReferenceField(
        Group, required=True, reverse_delete_rule=0)
    to_service = EmbeddedDocumentField(ServiceReference, required=True)

    def clean(self):
        if self.from_component not in self._instance.components:
            raise ValidationError(
                'Source component is not part of the application')
        if self.to_service.group not in self._instance.components:
            raise ValidationError(
                'Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class Application(NameMixin, StormDocument):

    components = ListField(StormReferenceField(Group))
    links = EmbeddedDocumentListField(ComponentLink)
    expose = EmbeddedDocumentListField(ServiceReference)

    meta = {
        'id_prefix': 'app-',
    }
