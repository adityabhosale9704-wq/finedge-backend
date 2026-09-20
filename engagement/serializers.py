from rest_framework import serializers

SUGGESTION_STATUS_CHOICES = ["New", "Reviewed", "Actioned"]


class ContestSerializer(serializers.Serializer):
    name = serializers.CharField()
    audience = serializers.CharField(required=False, allow_blank=True, default="")
    period_start = serializers.DateField(required=False, allow_null=True, default=None)
    period_end = serializers.DateField(required=False, allow_null=True, default=None)
    target_metric = serializers.CharField(required=False, allow_blank=True, default="")
    prize = serializers.CharField(required=False, allow_blank=True, default="")


class SuggestionSerializer(serializers.Serializer):
    submitted_by = serializers.CharField(required=False, allow_blank=True, default="Anonymous")
    text = serializers.CharField()
    status = serializers.ChoiceField(
        choices=SUGGESTION_STATUS_CHOICES, required=False, default="New"
    )
    response_note = serializers.CharField(required=False, allow_blank=True, default="")


class ActivitySerializer(serializers.Serializer):
    name = serializers.CharField()
    date_or_recurrence = serializers.CharField(required=False, allow_blank=True, default="")
    audience = serializers.CharField(required=False, allow_blank=True, default="")
