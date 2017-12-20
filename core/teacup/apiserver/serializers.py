from django.db import transaction

from rest_framework import serializers

from teacup.apiserver.models import Group, Service, Application, ComponentLink, Recipe, Trigger
from teacup.apiserver import validators


class ServiceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Service
        fields = ('name', 'protocol', 'port')


class GroupSerializer(serializers.ModelSerializer):

    query = serializers.JSONField(default=dict, validators=[validators.validate_dict])
    include = serializers.JSONField(read_only=True)
    exclude = serializers.JSONField(read_only=True)

    services = ServiceSerializer(many=True, allow_empty=True, default=list)

    class Meta:
        model = Group
        fields = ('name', 'query', 'include', 'exclude', 'services')

    def create(self, validated_data):
        services = validated_data.pop('services')

        instance = Group.objects.create(**validated_data)
        instance.services.set(services, bulk=False)

        return instance

    def update(self, instance, validated_data):
        services = validated_data.pop('services', None)

        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()

        if services is not None:
            instance.services.all().delete()
            instance.services.set(services, bulk=False)

        return instance

    def validate(self, data):
        if 'services' in data:
            validated_services = [Service(**item) for item in data['services']]
            data['services'] = validated_services

        return data


class GroupAddRemoveMembersSerializer(serializers.Serializer):

    include = serializers.JSONField(default=list)
    exclude = serializers.JSONField(default=list)


class ComponentLinkSerializer(serializers.ModelSerializer):

    src_component = serializers.SlugField(source='from_component.name')
    dest_component = serializers.SlugField(source='to_service.group.name')
    dest_service = serializers.SlugField(source='to_service.name')

    class Meta:
        model = ComponentLink
        fields = ('src_component', 'dest_component', 'dest_service')


class ExposedServiceSerializer(serializers.ModelSerializer):

    component = serializers.SlugField(source='group.name')
    service = serializers.SlugField(source='name')

    class Meta:
        model = Service
        fields = ('component', 'service')


class ApplicationSerializer(serializers.ModelSerializer):

    default_error_messages = {
        'unknown_group': 'Component {component} is not part of the application',
        'unknown_service': 'Service {service} is not part of component {component}',
    }

    components = serializers.SlugRelatedField(many=True, slug_field='name', queryset=Group.objects.all())

    links = ComponentLinkSerializer(many=True, allow_empty=True)
    expose = ExposedServiceSerializer(many=True, allow_empty=True)

    class Meta:
        model = Application
        fields = ('name', 'components', 'links', 'expose')

    @transaction.atomic
    def create(self, validated_data):
        components = validated_data.pop('components')
        links = validated_data.pop('links')
        expose = validated_data.pop('expose')

        instance = Application.objects.create(**validated_data)

        instance.components.set(components)
        instance.links.set(links, bulk=False)
        instance.expose.set(expose, bulk=False)

        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        components = validated_data.pop('components')
        links = validated_data.pop('links')
        expose = validated_data.pop('expose')

        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()

        instance.components.set(components)
        instance.links.all().delete()
        instance.links.set(links, bulk=False)
        instance.expose.set(expose, bulk=False)

        return instance

    def validate(self, data):
        validated_links = []

        components = {component.name: component for component in data['components']}

        for item in data['links']:
            from_component_name = item['from_component']['name']
            to_component_name = item['to_service']['group']['name']
            to_service_name = item['to_service']['name']

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
                from_component=from_component, to_service=to_service)

            validated_links.append(link)

        data['links'] = validated_links

        validated_expose = []

        for item in data['expose']:
            component_name = item['group']['name']
            service_name = item['name']

            try:
                component = components[component_name]
            except KeyError:
                self.fail('unknown_group', component=component_name)

            try:
                service = component.services.get(name=service_name)
            except Service.DoesNotExist:
                self.fail('unknown_service', service=service_name, component=component_name)

            validated_expose.append(service)

        data['expose'] = validated_expose

        return data


class TriggerSerializer(serializers.ModelSerializer):

    arguments = serializers.JSONField(default=dict)
    result = serializers.JSONField(default=dict)

    class Meta:
        model = Trigger
        fields = ('uuid', 'name', 'status', 'arguments', 'result', 'created', 'heartbeat')


class RecipeSerializer(serializers.ModelSerializer):

    default_error_messages = {
        'unknown_group': 'Group {group} does not exist',
    }

    options = serializers.JSONField(default=dict, validators=[validators.validate_dict])
    params = serializers.JSONField(default=dict, validators=[validators.validate_dict])

    targetAnyOf = serializers.SlugField(source='target_any_of.name', allow_null=True, required=False)
    targetAllIn = serializers.SlugField(source='target_all_in.name', allow_null=True, required=False)
    addTo = serializers.SlugField(source='add_to.name', allow_null=True, required=False)

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
