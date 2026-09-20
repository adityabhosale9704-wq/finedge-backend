from rest_framework import serializers

RELIEVING_STATUS_CHOICES = ["Pending", "Issued"]


class SeparationCreateSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    resignation_date = serializers.DateField()
    last_working_day = serializers.DateField()
    notice_period_days = serializers.IntegerField(required=False, default=30, min_value=0)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class SeparationUpdateSerializer(serializers.Serializer):
    relieving_letter_status = serializers.ChoiceField(
        choices=RELIEVING_STATUS_CHOICES, required=False
    )
    full_final_settlement_note = serializers.CharField(
        required=False, allow_blank=True
    )
