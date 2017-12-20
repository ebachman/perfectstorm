from django.db import models


class Message(models.Model):

    create_date = models.DateTimeField(auto_now_add=True)
    content = models.TextField()

    class Meta:
        ordering = ['-create_date']
