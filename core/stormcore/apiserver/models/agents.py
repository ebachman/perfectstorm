import time
from datetime import datetime, timedelta

from mongoengine import DateTimeField, StringField

from stormcore.apiserver.models.base import (
    StormDocument, TypeMixin, NameMixin, StormQuerySet, EscapedDictField)


CLEANUP_INTERVAL = 1
CLEANUP_TIMESTAMP = 0


def cleanup_expired_agents():
    global CLEANUP_TIMESTAMP
    now = time.time()
    if now - CLEANUP_TIMESTAMP < CLEANUP_INTERVAL:
        return
    Agent.objects.expired().update(status='offline')
    CLEANUP_TIMESTAMP = time.time()


class AgentQuerySet(StormQuerySet):

    def expired(self):
        threshold = datetime.now() - Agent.HEARTBEAT_DURATION
        return self.filter(heartbeat__lt=threshold)


class Agent(NameMixin, TypeMixin, StormDocument):

    HEARTBEAT_DURATION = timedelta(seconds=60)

    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
    )

    heartbeat = DateTimeField(default=datetime.now, required=True)

    status = StringField(
        choices=STATUS_CHOICES, default='offline', required=True)
    options = EscapedDictField()

    meta = {
        'id_prefix': 'agt-',
        'queryset_class': AgentQuerySet,
        'indexes': ['heartbeat'],
    }
