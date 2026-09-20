from rest_framework import serializers

WORKFLOW_TYPES = ["Recruitment", "Onboarding", "Exit"]


class WorkflowStepSerializer(serializers.Serializer):
    step_name = serializers.CharField()
    who = serializers.CharField(required=False, allow_blank=True, default="")
    tat_days = serializers.IntegerField(required=False, default=1, min_value=0)
    move = serializers.ChoiceField(choices=["up", "down"], required=False)
