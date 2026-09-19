from rest_framework import serializers


class TaskCreateSerializer(serializers.Serializer):
    title = serializers.CharField()
    department = serializers.CharField()
    assigned_to = serializers.CharField()
    tat_days = serializers.IntegerField(required=False, default=3, min_value=1)


class TaskUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    department = serializers.CharField(required=False)
    assigned_to = serializers.CharField(required=False)
    tat_days = serializers.IntegerField(required=False, min_value=1)
