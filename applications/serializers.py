from rest_framework import serializers
from .models import App


class AppSerializer(serializers.ModelSerializer):
    namespace_id = serializers.IntegerField(write_only=True)
    namespace = serializers.CharField(source='namespace.name', read_only=True)

    class Meta:
        model = App
        fields = ['id', 'name', 'namespace', 'namespace_id', 'image', 'replicas', 'cpu', 'memory']
