from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from applications.models import App

from .models import Backup, ScheduleBackup
from .tasks import perform_backup
from .serializers import BackupSerializer, ScheduleBackupSerializer
from croniter import croniter
from croniter.croniter import CroniterBadCronError
from clusterproject.metrics import hamamooz_backup_jobs_total

class BackupView(APIView):

    def post(self, request):
        app_id = request.data.get("app_id")
        source_path = request.data.get("source_path")
        schedule = request.data.get("schedule")

        if not app_id or not source_path:
            hamamooz_backup_jobs_total.labels("app", "create", "error", "").inc()
            return Response(
                {"error": "app_id and source_path are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            app = App.objects.select_related(
                "namespace",
                "namespace__cluster",
            ).get(id=app_id)
        except App.DoesNotExist:
            hamamooz_backup_jobs_total.labels("app", "create", "error", "").inc()
            return Response(
                {"error": "App not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Scheduled backup
        if schedule:
            try:
                croniter(schedule)
            except (CroniterBadCronError, ValueError):
                hamamooz_backup_jobs_total.labels("app", "create", "error", "").inc()
                return Response(
                    {
                        "error": "Invalid cron expression",
                        "schedule": schedule,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            already_exists = ScheduleBackup.objects.filter(
                app=app,
                source_path=source_path,
                schedule=schedule,
                active=True,
            ).exists()

            if already_exists:
                hamamooz_backup_jobs_total.labels("app", "create", "error", "").inc()
                return Response(
                    {
                        "error": (
                            "An active scheduled backup with the same "
                            "app, source path and schedule already exists"
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            scheduled_backup = ScheduleBackup.objects.create(
                app=app,
                source_path=source_path,
                schedule=schedule,
                active=True,
            )

            hamamooz_backup_jobs_total.labels("app", "create", "success", "").inc()
            return Response(
                {
                    "schedule_backup_id": str(scheduled_backup.id),
                    "status": "scheduled",
                    "created_at": scheduled_backup.created_at,
                    "active": scheduled_backup.active,
                },
                status=status.HTTP_201_CREATED,
            )

        # Instant backup
        backup = Backup.objects.create(
            app=app,
            source_path=source_path,
            status="pending",
            is_scheduled=False,
        )

        perform_backup.delay(str(backup.id))

        hamamooz_backup_jobs_total.labels("app", "create", "success", "").inc()
        return Response(
            {
                "backup_id": f"bkp_{backup.id}",
                "status": backup.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BackupStatusView(APIView):

    def get(self, request, backup_id):
        try:
            backup = Backup.objects.get(id=backup_id)
        except Backup.DoesNotExist:
            hamamooz_backup_jobs_total.labels("app", "list", "error", "").inc()
            return Response(
                {"error": "Backup not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BackupSerializer(backup)
        hamamooz_backup_jobs_total.labels("app", "list", "success", "").inc()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class AppBackupListView(APIView):

    def get(self, request, app_id):
        if not App.objects.filter(id=app_id).exists():
            hamamooz_backup_jobs_total.labels("app", "list", "error", "").inc()
            return Response(
                {"error": "App not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        backups = Backup.objects.filter(
            app_id=app_id
        ).order_by("-created_at")

        serializer = BackupSerializer(
            backups,
            many=True,
        )

        hamamooz_backup_jobs_total.labels("app", "list", "success", "").inc()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ScheduleBackupDeactivateView(APIView):

    def patch(self, request, schedule_id):
        try:
            scheduled_backup = ScheduleBackup.objects.get(
                id=schedule_id
            )
        except ScheduleBackup.DoesNotExist:
            hamamooz_backup_jobs_total.labels("app", "update", "error", "").inc()
            return Response(
                {"error": "Scheduled backup not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not scheduled_backup.active:
            hamamooz_backup_jobs_total.labels("app", "update", "success", "").inc()
            return Response(
                {
                    "schedule_backup_id": str(scheduled_backup.id),
                    "status": "already_deactivated",
                    "active": False,
                },
                status=status.HTTP_200_OK,
            )

        scheduled_backup.active = False
        scheduled_backup.save(update_fields=["active"])

        hamamooz_backup_jobs_total.labels("app", "update", "success", "").inc()
        return Response(
            {
                "schedule_backup_id": str(scheduled_backup.id),
                "status": "deactivated",
                "active": False,
            },
            status=status.HTTP_200_OK,
        )


class AppScheduleBackupListView(APIView):

    def get(self, request, app_id):
        if not App.objects.filter(id=app_id).exists():
            hamamooz_backup_jobs_total.labels("app", "list", "error", "").inc()
            return Response(
                {"error": "App not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        schedules = ScheduleBackup.objects.filter(
            app_id=app_id
        ).order_by("-created_at")

        serializer = ScheduleBackupSerializer(
            schedules,
            many=True,
        )

        hamamooz_backup_jobs_total.labels("app", "list", "success", "").inc()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )