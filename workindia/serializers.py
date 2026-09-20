from rest_framework import serializers

CALL_STATUS_CHOICES = ["Not Reached", "Interested", "Not Interested", "Callback Requested"]


class WorkIndiaPromoteSerializer(serializers.Serializer):
    requisition_id = serializers.CharField()


class WorkIndiaLogCallSerializer(serializers.Serializer):
    call_status = serializers.ChoiceField(choices=CALL_STATUS_CHOICES)
    call_notes = serializers.CharField(required=False, allow_blank=True, default="")
    interview_datetime = serializers.DateTimeField(required=False, allow_null=True, default=None)
