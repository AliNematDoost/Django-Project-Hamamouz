from django.db import models
from namespaces.models import Namespace


class App(models.Model):
    namespace = models.ForeignKey(
        Namespace, on_delete=models.CASCADE, related_name="apps"
    )
    name = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    replicas = models.PositiveIntegerField(default=1)
    cpu = models.CharField(max_length=20, default="250m")
    memory = models.CharField(max_length=20, default="256Mi")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("namespace", "name")

    def __str__(self):
        return f"{self.namespace.name}/{self.name}"
