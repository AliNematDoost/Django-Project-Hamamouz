from django.urls import path

from .views import (
    BackupView,
    BackupStatusView,
    AppBackupListView,
    ScheduleBackupDeactivateView,
    AppScheduleBackupListView,
)

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
    path(
        "backup/schedule/<uuid:schedule_id>",
        ScheduleBackupDeactivateView.as_view(),
        name="schedule-backup-deactivate",
    ),
    path(
        "backup/schedule/app/<int:app_id>",
        AppScheduleBackupListView.as_view(),
        name="app-schedule-backup-list",
    ),
]