from django.db import models


class Cluster(models.Model):
    name = models.CharField(max_length=255, unique=True)
    identity = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
