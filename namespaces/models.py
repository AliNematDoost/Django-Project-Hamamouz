from django.db import models
from clusters.models import Cluster


class Namespace(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='namespaces')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cluster', 'name')

    def __str__(self):
        return f"{self.cluster.name}/{self.name}"
