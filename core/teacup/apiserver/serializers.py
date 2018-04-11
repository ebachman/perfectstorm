# Copyright (c) 2017, Composure.ai
# Copyright (c) 2018, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

from rest_framework.serializers import (
    CharField,
    Field,
    ListField,
    Serializer,
    SlugField,
)

from rest_framework_mongoengine.fields import ReferenceField
from rest_framework_mongoengine.serializers import DocumentSerializer, EmbeddedDocumentSerializer
from rest_framework_mongoengine.validators import UniqueValidator

from teacup.apiserver.models import (
    Agent,
    Application,
    ComponentLink,
    Group,
    Procedure,
    Resource,
    Service,
    ServiceReference,
    Trigger,
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

        return document.id

    def to_representation(self, value):
        return self.pk_field.to_representation(value)


class EscapedDynamicField(Field):

    def to_representation(self, value):
        return value

    def to_internal_value(self, value):
        return value


class AgentSerializer(DocumentSerializer):

    class Meta:
        model = Agent
        fields = ('id', 'type', 'heartbeat')


class ResourceSerializer(DocumentSerializer):

    owner = StormReferenceField(Agent)
    snapshot = EscapedDynamicField(default=dict)

    class Meta:
        model = Resource
        fields = ('id', 'type', 'names', 'owner', 'parent', 'image', 'status', 'health', 'snapshot')


class GroupSerializer(DocumentSerializer):

    name = CharField(allow_blank=False, allow_null=True, required=False, validators=[UniqueValidator(Group.objects.all())])

    query = EscapedDynamicField(default=dict)

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
        'unknown_group': 'Component {component} is not part of the application',
        'unknown_service': 'Service {service} is not part of component {component}',
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

        components = {component.name: component for component in data['components']}

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
                self.fail('unknown_service', service=to_service_name, component=to_component_name)

            link = ComponentLink(
                from_component=from_component, to_service=to_service.to_reference())

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
                self.fail('unknown_service', service=service_name, component=component_name)

            validated_expose.append(service.to_reference())

        data['expose'] = validated_expose

        return data


class ProcedureSerializer(DocumentSerializer):

    options = EscapedDynamicField(default=dict)
    params = EscapedDynamicField(default=dict)
    target = StormReferenceField(Resource, allow_null=True)

    class Meta:
        model = Procedure
        fields = ('id', 'type', 'name', 'content', 'options', 'params', 'target')
        read_only_fields = ('id',)


class BaseTriggerSerializer(DocumentSerializer):

    procedure = StormReferenceField(Procedure)

    options = EscapedDynamicField(default=dict)
    params = EscapedDynamicField(default=dict)
    result = EscapedDynamicField(default=dict)
    target = StormReferenceField(Resource, allow_null=True)

    class Meta:
        model = Trigger
        fields = ('id', 'type', 'owner', 'status', 'procedure', 'content', 'options', 'params',
                  'result', 'target', 'created')


class CreateTriggerSerializer(BaseTriggerSerializer):

    class Meta(BaseTriggerSerializer.Meta):
        read_only_fields = ('id', 'owner', 'status', 'created')


class TriggerSerializer(BaseTriggerSerializer):

    class Meta(BaseTriggerSerializer.Meta):
        read_only_fields = BaseTriggerSerializer.Meta.fields


class TriggerHandleSerializer(Serializer):

    agent = StormReferenceField(Agent)


class TriggerCompleteSerializer(Serializer):

    result = EscapedDynamicField(default=dict)
