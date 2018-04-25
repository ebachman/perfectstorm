from mongoengine import StringField, ListField

from stormcore.apiserver.models.base import (
    StormDocument, TypeMixin, StormReferenceField, EscapedDictField)


class Resource(TypeMixin, StormDocument):

    STATUS_CHOICES = (
        ('unknown', 'Unknown'),
        ('creating', 'Creating'),
        ('created', 'Created'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('updating', 'Updating'),
        ('updated', 'Updated'),
        ('stopping', 'Stopped'),
        ('stopped', 'Stopped'),
        ('removing', 'Removing'),
        ('error', 'Error'),
    )

    HEALTH_CHOICES = (
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
    )

    names = ListField(StringField(min_length=1))
    owner = StormReferenceField('Agent', required=True)

    parent = StormReferenceField('Resource', null=True)
    cluster = StormReferenceField('Resource', null=True)
    host = StormReferenceField('Resource', null=True)
    image = StringField(min_length=1, null=True)

    status = StringField(
        choices=STATUS_CHOICES, default='unknown', required=True)
    health = StringField(
        choices=HEALTH_CHOICES, default='unknown', required=True)

    snapshot = EscapedDictField()

    meta = {
        'id_prefix': 'res-',
        'indexes': [
            'names',
            'owner',
            'status',
            'health',
        ],
        'ordering': ['type', 'names'],
        'lookup_fields': ['names'],
    }

    def __str__(self):
        return self.names[0] if self.names else str(self.pk)
