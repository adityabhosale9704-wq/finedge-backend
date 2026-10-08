from rest_framework import serializers

DOC_STATUS_CHOICES = ["Pending", "Verified", "Rejected"]
MARITAL_STATUS_CHOICES = ["Married", "Unmarried"]


class DocRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AdditionalDocsSerializer(serializers.Serializer):
    uan_number = serializers.CharField(required=False, allow_blank=True)
    marital_status = serializers.ChoiceField(choices=MARITAL_STATUS_CHOICES, required=False)
