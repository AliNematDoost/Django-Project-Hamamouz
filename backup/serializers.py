from rest_framework import serializers

from .models import Backup


class BackupSerializer(serializers.ModelSerializer):
    backup_id = serializers.SerializerMethodField()

    class Meta:
        model = Backup
        fields = [
            "backup_id",
            "status",
            "output_path",
            "error",
            "created_at",
            "completed_at",
        ]

    def get_backup_id(self, obj):
        return f"bkp_{obj.id}"