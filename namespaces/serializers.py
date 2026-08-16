from rest_framework import serializers
from .models import Namespace


class NamespaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Namespace
        fields = ['id', 'name', 'cluster', 'created_at']
