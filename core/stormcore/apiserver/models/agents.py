import time
from datetime import datetime, timedelta

from mongoengine import DateTimeField, StringField

from stormcore.apiserver.models.base import (
    StormDocument, TypeMixin, NameMixin, StormQuerySet, EscapedDictField)
from stormcore.apiserver.models.procedures import Job
from stormcore.apiserver.models.resources import Resource


CLEANUP_INTERVAL = 1
CLEANUP_TIMESTAMP = 0


def cleanup_expired_agents():
    global CLEANUP_TIMESTAMP
    now = time.time()
    if now - CLEANUP_TIMESTAMP < CLEANUP_INTERVAL:
        return
    Agent.objects.expired().update(status='offline')
    CLEANUP_TIMESTAMP = time.time()


def cleanup_owned_documents(deleted_agent_ids):
    if not deleted_agent_ids:
        return

    orphaned_resources = Resource.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_resources.delete()

    orphaned_jobs = Job.objects.filter(
        owner__in=deleted_agent_ids)
    orphaned_jobs.update(status='pending', owner=None)


class AgentQuerySet(StormQuerySet):

    def expired(self):
        threshold = datetime.now() - Agent.HEARTBEAT_DURATION
        return self.filter(heartbeat__lt=threshold)

    def delete(self, *args, **kwargs):
        queryset = self.clone()
        agent_ids = list(queryset.values_list('pk'))
        cleanup_owned_documents(agent_ids)

        super().delete(*args, **kwargs)


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

    def delete(self):
        cleanup_owned_documents([self.pk])
        super().delete()
