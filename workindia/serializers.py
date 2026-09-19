from rest_framework import serializers


class WorkIndiaPromoteSerializer(serializers.Serializer):
    requisition_id = serializers.CharField()
