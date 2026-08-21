from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from applications.models import App

from .models import Backup
from .tasks import perform_backup
from .serializers import BackupSerializer


class BackupView(APIView):

    def post(self, request):
        app_id = request.data.get("app_id")
        source_path = request.data.get("source_path")
        pod_name = request.data.get("pod_name")

        if not app_id or not source_path or not pod_name:
            return Response(
                {
                    "error": "app_id, pod_name and source_path are required"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            app = App.objects.select_related(
                "namespace",
                "namespace__cluster",
            ).get(id=app_id)
        except App.DoesNotExist:
            return Response(
                {"error": "App not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        backup = Backup.objects.create(
            app=app,
            pod_name=pod_name,
            source_path=source_path,
            status="pending",
        )

        perform_backup.delay(str(backup.id))

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
            return Response(
                {"error": "Backup not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BackupSerializer(backup)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )