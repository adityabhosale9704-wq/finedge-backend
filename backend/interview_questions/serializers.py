from rest_framework import serializers

QUESTION_TYPE_CHOICES = [
    "Technical",
    "Behavioural",
    "Situational",
    "Role-specific",
    "Culture fit",
]


class InterviewQuestionSerializer(serializers.Serializer):
    department = serializers.CharField(required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=QUESTION_TYPE_CHOICES)
    question_text = serializers.CharField()
