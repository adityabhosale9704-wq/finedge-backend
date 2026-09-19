from rest_framework import serializers

POSITION_STATUS_CHOICES = ["Active", "Vacant"]


class PositionCreateSerializer(serializers.Serializer):
    designation = serializers.CharField()
    department = serializers.CharField()
    branch = serializers.CharField()
    status = serializers.ChoiceField(
        choices=POSITION_STATUS_CHOICES, required=False, default="Vacant"
    )


class PositionUpdateSerializer(serializers.Serializer):
    designation = serializers.CharField(required=False)
    department = serializers.CharField(required=False)
    branch = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=POSITION_STATUS_CHOICES, required=False)


class PositionAssignSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
