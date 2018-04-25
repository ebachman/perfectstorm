from datetime import datetime

from mongoengine import (
    Document, QuerySet, StringField, DateTimeField, ListField, signals)

from stormcore.apiserver.models.base import (
    StormDocument, NameMixin, AutoIncrementField)
from stormcore.apiserver.models.procedures import Subscription
from stormcore.apiserver.models.resources import Resource


class EventQuerySet(QuerySet):

    def record_event(self, event_type, obj):
        if not isinstance(obj, StormDocument):
            return

        names = []
        if isinstance(obj, NameMixin):
            if obj.name is not None:
                names.append(obj.name)
        elif isinstance(obj, Resource):
            names.extend(obj.names)

        ev = Event(
            event_type=event_type,
            entity_type=type(obj).__name__.lower(),
            entity_id=obj.id,
            entity_names=names,
        )

        ev.save()
        Subscription.objects.exec_for_event(ev)

        return ev


class Event(Document):

    MAX_EVENTS = 10000

    EVENT_TYPE_CHOICES = [
        'created',
        'updated',
        'deleted',
    ]

    id = AutoIncrementField(primary_key=True)
    date = DateTimeField(default=datetime.now)

    event_type = StringField(choices=EVENT_TYPE_CHOICES, required=True)
    entity_type = StringField(required=True)
    entity_id = StringField(required=True)
    entity_names = ListField(StringField())

    meta = {
        'queryset_class': EventQuerySet,
        'ordering': ['id'],
        'max_documents': MAX_EVENTS,
        'max_size': 8 * 1024 * MAX_EVENTS,
    }


def on_save(sender, document, created=False, **kwargs):
    event_type = 'created' if created else 'updated'
    Event.objects.record_event(event_type, document)


def on_delete(sender, document, **kwargs):
    Event.objects.record_event('deleted', document)


signals.post_save.connect(on_save)
signals.post_delete.connect(on_delete)
