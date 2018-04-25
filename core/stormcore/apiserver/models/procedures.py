import collections
from datetime import datetime

from mongoengine import StringField, DateTimeField

from stormcore.apiserver.models.base import (
    StormDocument, StormQuerySet, TypeMixin, NameMixin,
    StormReferenceField, EscapedDictField)
from stormcore.apiserver.models.groups import Group
from stormcore.apiserver.models.resources import Resource


class Procedure(NameMixin, TypeMixin, StormDocument):

    content = StringField(required=True, default='')
    options = EscapedDictField()
    params = EscapedDictField()

    meta = {
        'id_prefix': 'prc-',
    }

    def exec(self, target, options=None, params=None):
        from stormcore.apiserver import templates

        if params is None:
            params = {}
        if options is None:
            options = {}

        merged_options = {**self.options, **options}
        merged_params = {**self.params, **params}

        rendered_content = templates.render(
            self.content, target, merged_params)

        job = Job(
            target=target,
            procedure=self,
            content=rendered_content,
            options=merged_options,
            params=merged_params,
        )

        job.save()
        return job


class SubscriptionQuerySet(StormQuerySet):

    def exec_for_event(self, event):
        for subscription in self.iter_for_event(event):
            subscription.exec(event)

    def iter_for_event(self, event):
        group_map = collections.defaultdict(list)

        for subscription in self:
            if subscription.group is None:
                # Dangling reference
                continue
            group_map[subscription.group.id].append(subscription)

        for sub_list in group_map.values():
            group = sub_list[0].group
            if group.members().filter(id=event.entity_id):
                yield from sub_list


class Subscription(StormDocument):

    group = StormReferenceField(Group)
    procedure = StormReferenceField(Procedure)

    target = StormReferenceField(Resource)
    options = EscapedDictField()
    params = EscapedDictField()

    meta = {
        'id_prefix': 'sub-',
        'queryset_class': SubscriptionQuerySet,
    }

    def exec(self, event):
        params = self.params
        if 'event' not in params:
            from stormcore.apiserver import templates
            params = self.params.copy()
            params['event'] = templates.JinjaEvents()._serialize(event)

        return self.procedure.exec(
            target=self.target,
            options=self.options,
            params=params,
        )


class Job(StormDocument):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
    )

    owner = StormReferenceField('Agent', null=True)

    target = StormReferenceField('Resource')
    procedure = StormReferenceField(Procedure)

    content = StringField()
    options = EscapedDictField()
    params = EscapedDictField()

    status = StringField(
        choices=STATUS_CHOICES, default='pending', required=True)
    result = EscapedDictField(required=True)

    created = DateTimeField(default=datetime.now, required=True)

    meta = {
        'id_prefix': 'job-',
        'indexes': [
            'created',
            'owner',
        ],
        'ordering': ['created'],
    }

    def __str__(self):
        return str(self.pk)
