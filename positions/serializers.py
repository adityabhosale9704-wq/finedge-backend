from rest_framework import serializers

POSITION_STATUS_CHOICES = ["Active", "Vacant"]


class PositionCreateSerializer(serializers.Serializer):
    designation = serializers.CharField()
    department = serializers.CharField()
    branch = serializers.CharField()
    # status is deliberately not settable here: a position's status is always
    # derived from whether it currently has an assigned employee, and must
    # only change via the assign/unassign endpoints. Every new position
    # starts Vacant.


class PositionUpdateSerializer(serializers.Serializer):
    designation = serializers.CharField(required=False)
    department = serializers.CharField(required=False)
    branch = serializers.CharField(required=False)
    # status intentionally omitted — see PositionCreateSerializer comment.
    # Setting it directly here used to let a position get stuck "Active"
    # with no current_employee_id, which neither /assign/ nor /unassign/
    # could then recover from.


class PositionAssignSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
