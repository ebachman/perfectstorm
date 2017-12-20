import json
import uuid
from datetime import datetime, timedelta

from django import forms
from django.db import models

from jsonfield import JSONField

from teacup.apiserver import graph, validators


class Group(models.Model):

    name = models.SlugField(unique=True)

    query = JSONField(default=dict, validators=[validators.validate_dict])
    include = JSONField(default=list, validators=[validators.validate_list_of_strings])
    exclude = JSONField(default=list, validators=[validators.validate_list_of_strings])

    class Meta:
        ordering = ('name',)

    def members(self, filter=None):
        query = graph.Nil()

        if self.query:
            query |= graph.parse_query(self.query)

        if self.include:
            query |= graph.ObjectIdIn(self.include)

        if self.exclude:
            query &= graph.ObjectIdNotIn(self.exclude)

        if filter is not None:
            query &= filter

        return graph.run_query(query)

    def __str__(self):
        return self.name


class Service(models.Model):

    PROTOCOL_CHOICES = (
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
    )

    name = models.SlugField()
    group = models.ForeignKey(Group, related_name='services', on_delete=models.CASCADE)

    protocol = models.CharField(max_length=8, choices=PROTOCOL_CHOICES)
    port = models.PositiveIntegerField()

    class Meta:
        unique_together = ('name', 'group')
        ordering = ('name',)

    def __str__(self):
        return '{}[{}]'.format(self.group.name, self.name)


class Application(models.Model):

    name = models.SlugField(unique=True)

    components = models.ManyToManyField(Group)
    expose = models.ManyToManyField(Service)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class ComponentLink(models.Model):

    application = models.ForeignKey(Application, related_name='links', on_delete=models.CASCADE)
    from_component = models.ForeignKey(Group, on_delete=models.CASCADE)
    to_service = models.ForeignKey(Service, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('application', 'from_component', 'to_service')

    def clean(self):
        if self.from_component not in self.application.components.all():
            raise ValidationError('Source component is not part of the application')
        if self.to_service.component not in self.application.components.all():
            raise ValidationError('Destination service is not part of the application')

    def __str__(self):
        return '{} -> {}'.format(self.from_component, self.to_service)


class TriggerQuerySet(models.QuerySet):

    def stale(self):
        threshold = datetime.now() - Trigger.HEARTBEAT_DURATION
        return self.filter(status='running', heartbeat__lt=threshold)


class Trigger(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    HEARTBEAT_DURATION = timedelta(seconds=60)

    name = models.SlugField()
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')

    arguments = JSONField(default=dict)
    result = JSONField(default=dict)

    created = models.DateTimeField(auto_now_add=True)
    heartbeat = models.DateTimeField(auto_now_add=True)

    objects = TriggerQuerySet.as_manager()

    class Meta:
        ordering = ('created',)


class Recipe(models.Model):

    type = models.SlugField()
    name = models.SlugField(unique=True)
    content = models.TextField(default='')

    options = JSONField(default=dict)
    params = JSONField(default=dict)

    target_any_of = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL, related_name='+')
    target_all_in = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL, related_name='+')
    add_to = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.type)
