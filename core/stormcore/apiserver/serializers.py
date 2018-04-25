from mongoengine import Document

from rest_framework.serializers import (
    CharField,
    Field,
    ListField,
    Serializer,
    SlugField,
)

from rest_framework_mongoengine.fields import ReferenceField
from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer)
from rest_framework_mongoengine.validators import UniqueValidator

from stormcore.apiserver.models import (
    Agent,
    Application,
    ComponentLink,
    Event,
    Group,
    Job,
    Procedure,
    Resource,
    Service,
    ServiceReference,
)


class StormReferenceField(ReferenceField):

    pk_field_class = CharField

    def to_internal_value(self, value):
        value = self.parse_id(value)
        queryset = self.get_queryset()

        try:
            document = queryset.only('id').lookup(value)
        except Exception:
            self.fail('not_found', pk_value=value)

        return document

    def to_representation(self, value):
        if isinstance(value, Document):
            return value.id
        return value


class EscapedDictField(Field):

    default_error_messages = {
        'wrong_type': 'Expected a JSON object.',
    }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', dict)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, value):
        if not isinstance(value, dict):
            self.fail('wrong_type')
        return value

    def to_representation(self, value):
        return value


class AgentSerializer(DocumentSerializer):

    name = CharField(
        allow_blank=False, allow_null=True, required=False,
        validators=[UniqueValidator(Agent.objects.all())])

    options = EscapedDictField()

    class Meta:
        model = Agent
        fields = ('id', 'type', 'name', 'heartbeat', 'status', 'options')


class ResourceSerializer(DocumentSerializer):

    owner = StormReferenceField(Agent)
    parent = StormReferenceField(Resource, allow_null=True, required=False)
    cluster = StormReferenceField(Resource, allow_null=True, required=False)
    host = StormReferenceField(Resource, allow_null=True, required=False)
    snapshot = EscapedDictField()

    class Meta:
        model = Resource
        fields = (
            'id', 'type', 'names', 'owner', 'parent', 'cluster', 'host',
            'image', 'status', 'health', 'snapshot')


class GroupSerializer(DocumentSerializer):

    name = CharField(
        allow_blank=False, allow_null=True, required=False,
        validators=[UniqueValidator(Group.objects.all())])

    query = EscapedDictField()

    include = ListField(child=CharField(), default=list)
    exclude = ListField(child=CharField(), default=list)

    class Meta:
        model = Group
        fields = ('id', 'name', 'query', 'include', 'exclude', 'services')


class GroupAddRemoveMembersSerializer(Serializer):

    include = ListField(child=CharField(), default=list)
    exclude = ListField(child=CharField(), default=list)


class ComponentLinkSerializer(EmbeddedDocumentSerializer):

    src_component = SlugField(source='from_component.name')
    dest_component = SlugField(source='to_service.group.name')
    dest_service = SlugField(source='to_service.service_name')

    class Meta:
        model = ComponentLink
        fields = ('src_component', 'dest_component', 'dest_service')


class ExposedServiceSerializer(EmbeddedDocumentSerializer):

    component = SlugField(source='group.name')
    service = SlugField(source='service_name')

    class Meta:
        model = ServiceReference
        fields = ('component', 'service')


class ApplicationSerializer(DocumentSerializer):

    default_error_messages = {
        'unknown_group':
            'Component {component} is not part of the application',
        'unknown_service':
            'Service {service} is not part of component {component}',
    }

    components = ListField(child=StormReferenceField(Group))

    links = ComponentLinkSerializer(many=True, allow_empty=True)
    expose = ExposedServiceSerializer(many=True, allow_empty=True)

    class Meta:
        model = Application
        fields = ('id', 'name', 'components', 'links', 'expose')

    def create(self, validated_data):
        return Application.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()
        return instance

    def validate(self, data):
        validated_links = []

        components = {
            component.name: component for component in data['components']}

        for item in data['links']:
            from_component_name = item['from_component']['name']
            to_component_name = item['to_service']['group']['name']
            to_service_name = item['to_service']['service_name']

            try:
                from_component = components[from_component_name]
            except KeyError:
                self.fail('unknown_group', component=from_component_name)

            try:
                to_component = components[to_component_name]
            except KeyError:
                self.fail('unknown_group', component=to_component_name)

            try:
                to_service = to_component.services.get(name=to_service_name)
            except Service.DoesNotExist:
                self.fail(
                    'unknown_service',
                    service=to_service_name,
                    component=to_component_name)

            link = ComponentLink(
                from_component=from_component,
                to_service=to_service.to_reference())

            validated_links.append(link)

        data['links'] = validated_links

        validated_expose = []

        for item in data['expose']:
            component_name = item['group']['name']
            service_name = item['service_name']

            try:
                component = components[component_name]
            except KeyError:
                self.fail('unknown_group', component=component_name)

            try:
                service = component.services.get(name=service_name)
            except Service.DoesNotExist:
                self.fail(
                    'unknown_service',
                    service=service_name,
                    component=component_name)

            validated_expose.append(service.to_reference())

        data['expose'] = validated_expose

        return data


class ProcedureSerializer(DocumentSerializer):

    name = CharField(
        allow_blank=False, allow_null=True, required=False,
        validators=[UniqueValidator(Procedure.objects.all())])

    options = EscapedDictField()
    params = EscapedDictField()

    class Meta:
        model = Procedure
        fields = ('id', 'type', 'name', 'content', 'options', 'params')
        extra_kwargs = {
            'content': {'required': False, 'allow_blank': True, 'default': ''},
        }


class ProcedureExecSerializer(Serializer):

    target = StormReferenceField(Resource)
    options = EscapedDictField()
    params = EscapedDictField()



class JobSerializer(DocumentSerializer):

    target = StormReferenceField(Resource)
    procedure = StormReferenceField(Procedure)

    options = EscapedDictField()
    params = EscapedDictField()
    result = EscapedDictField()

    class Meta:
        model = Job
        fields = (
            'id', 'owner', 'target', 'procedure',
            'content', 'options', 'params',
            'status', 'result', 'created',
        )


class JobHandleSerializer(Serializer):

    owner = StormReferenceField(Agent)


class JobCompleteSerializer(Serializer):

    result = EscapedDictField()


class EventSerializer(DocumentSerializer):

    class Meta:
        model = Event
        fields = (
            'id', 'event_type', 'entity_type', 'entity_id', 'entity_names',
        )
