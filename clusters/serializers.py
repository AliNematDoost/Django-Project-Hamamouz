from rest_framework import serializers
from .models import Cluster


class ClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = ['id', 'address', 'name', 'token']
        extra_kwargs = {'token': {'write_only': True}}
