from rest_framework import serializers

from .models import Backup, ScheduleBackup


class BackupSerializer(serializers.ModelSerializer):
    backup_id = serializers.SerializerMethodField()

    class Meta:
        model = Backup
        fields = [
            "backup_id",
            "status",
            "pod_name",
            "error",
            "output_path",
            "is_scheduled"
        ]

    def get_backup_id(self, obj):
        return f"bkp_{obj.id}"

class ScheduleBackupSerializer(serializers.ModelSerializer):
    schedule_backup_id = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleBackup
        fields = [
            "schedule_backup_id",
            "schedule",
            "source_path",
            "pod_name",
            "created_at",
            "active",
        ]

    def get_schedule_backup_id(self, obj):
        return str(obj.id)