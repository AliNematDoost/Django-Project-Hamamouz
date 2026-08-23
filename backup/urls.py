from django.urls import path

from .views import BackupView, BackupStatusView, AppBackupListView


urlpatterns = [
    path("backup", BackupView.as_view(), name="backup"),
    path(
        "backup/<uuid:backup_id>",
        BackupStatusView.as_view(),
        name="backup-status",
    ),
    path(
        "backup/app/<int:app_id>",
        AppBackupListView.as_view(),
        name="app-backup-list",
    ),
]