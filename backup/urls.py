from django.urls import path

from .views import BackupView, BackupStatusView


urlpatterns = [
    path("backup", BackupView.as_view(), name="backup"),
    path(
        "backup/<uuid:backup_id>",
        BackupStatusView.as_view(),
        name="backup-status",
    ),
]