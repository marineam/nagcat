from django.db import models

class URL(models.Model):
    content = models.CharField(max_length=10000)

    def __unicode__(self):
        return self.content
