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
    JSONField,
    ListField,
    ModelSerializer,
    Serializer,
    SlugField,
    SlugRelatedField,
)

from rest_framework_mongoengine.serializers import (
    DocumentSerializer,
    DynamicDocumentSerializer,
    EmbeddedDocumentSerializer,
)

from teacup.apiserver.models import (
    Application,
    ComponentLink,
    Group,
    Recipe,
    Resource,
    Service,
    ServiceReference,
    Trigger,
)

from teacup.apiserver import validators


class EscapedDynamicField(Field):

    def to_representation(self, value):
        return value

    def to_internal_value(self, value):
        return value


class ResourceSerializer(DynamicDocumentSerializer):

    snapshot = EscapedDynamicField()

    class Meta:
        model = Resource
        fields = ('type', 'names', 'host', 'image', 'snapshot')

    def to_internal_value(self, data):
        try:
            del data['pk']
        except (AttributeError, KeyError):
            pass

        return super().to_internal_value(data)


class GroupSerializer(DocumentSerializer):

    query = EscapedDynamicField()

    class Meta:
        model = Group
        fields = ('name', 'query', 'include', 'exclude', 'services')


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

    components = SlugRelatedField(many=True, slug_field='name', queryset=Group.objects.all())

    links = ComponentLinkSerializer(many=True, allow_empty=True)
    expose = ExposedServiceSerializer(many=True, allow_empty=True)

    class Meta:
        model = Application
        fields = ('name', 'components', 'links', 'expose')

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
                from_component=from_component, to_service=to_service.reference())

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

            validated_expose.append(service.reference())

        data['expose'] = validated_expose

        return data


class TriggerSerializer(ModelSerializer):

    arguments = JSONField(default=dict)
    result = JSONField(default=dict)

    class Meta:
        model = Trigger
        fields = ('uuid', 'name', 'status', 'arguments', 'result', 'created', 'heartbeat')


class RecipeSerializer(ModelSerializer):

    default_error_messages = {
        'unknown_group': 'Group {group} does not exist',
    }

    options = JSONField(default=dict, validators=[validators.validate_dict])
    params = JSONField(default=dict, validators=[validators.validate_dict])

    targetAnyOf = SlugField(source='target_any_of.name', allow_null=True, required=False)
    targetAllIn = SlugField(source='target_all_in.name', allow_null=True, required=False)
    addTo = SlugField(source='add_to.name', allow_null=True, required=False)

    class Meta:
        model = Recipe
        fields = ('name', 'type', 'content', 'options', 'params', 'targetAnyOf', 'targetAllIn', 'addTo')

    def validate(self, data):
        def validate_group(key):
            group = None

            try:
                group_name = data[key]['name']
            except KeyError:
                pass
            else:
                if group_name is not None:
                    try:
                        group = Group.objects.get(name=group_name)
                    except Group.DoesNotExist:
                        self.fail('unknown_group', group=group_name)

            data[key] = group

        validate_group('target_any_of')
        validate_group('target_all_in')
        validate_group('add_to')

        return data
