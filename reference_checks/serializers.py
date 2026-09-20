from rest_framework import serializers

REFERENCE_CHECK_STATUS_CHOICES = ["Pending", "Positive", "Discrepancy"]


class ReferenceCheckSerializer(serializers.Serializer):
    candidate_id = serializers.CharField()
    referee_name = serializers.CharField()
    relationship_to_candidate = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=REFERENCE_CHECK_STATUS_CHOICES, required=False, default="Pending"
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ReferenceCheckUpdateSerializer(serializers.Serializer):
    referee_name = serializers.CharField(required=False)
    relationship_to_candidate = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=REFERENCE_CHECK_STATUS_CHOICES, required=False)
    note = serializers.CharField(required=False, allow_blank=True)
