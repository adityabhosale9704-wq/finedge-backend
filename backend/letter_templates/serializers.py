from rest_framework import serializers

LETTER_TYPES = [
    "Offer Letter",
    "Appointment Letter",
    "Confirmation Letter",
    "Increment Letter",
    "Relieving-cum-Experience Letter",
]


class LetterTemplateSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, allow_blank=True, default="")
    body = serializers.CharField()
