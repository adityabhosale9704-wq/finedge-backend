from rest_framework import serializers


class PolicySerializer(serializers.Serializer):
    title = serializers.CharField()
    body = serializers.CharField(required=False, allow_blank=True, default="")
