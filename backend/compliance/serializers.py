from rest_framework import serializers


class ComplianceItemSerializer(serializers.Serializer):
    act_name = serializers.CharField()
    frequency = serializers.CharField(required=False, allow_blank=True, default="")
    owner = serializers.CharField(required=False, allow_blank=True, default="")
    next_due_date = serializers.DateField()
