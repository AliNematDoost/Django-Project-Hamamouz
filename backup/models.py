import uuid

from django.db import models
from applications.models import App


class Backup(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app = models.ForeignKey(
        App,
        on_delete=models.CASCADE,
        related_name="backups",
    )
    pod_name = models.CharField(max_length=255)
    source_path = models.TextField()
    output_path = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_scheduled = models.BooleanField(default=False)

class ScheduleBackup(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    app = models.ForeignKey(
        App,
        on_delete=models.CASCADE,
        related_name="scheduled_backups",
    )

    pod_name = models.CharField(max_length=255)
    source_path = models.TextField()

    # Cron expression, e.g. "0 20 * * *"
    schedule = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)