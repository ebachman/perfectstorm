from datetime import datetime

from mongoengine import StringField, DateTimeField

from stormcore.apiserver.models.base import (
    StormDocument, TypeMixin, NameMixin, StormReferenceField, EscapedDictField)


class Procedure(NameMixin, TypeMixin, StormDocument):

    content = StringField(required=True, default='')
    options = EscapedDictField()
    params = EscapedDictField()

    meta = {
        'id_prefix': 'prc-',
    }


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
