from rest_framework import serializers
from .models import Cluster


class ClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = ["id", "address", "name", "token"]
        extra_kwargs = {"token": {"write_only": True}}


class ClusterTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = ["token"]

    def validate_token(self, value):
        if not value.strip():
            raise serializers.ValidationError("Token cannot be empty.")
        return value
