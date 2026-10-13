from rest_framework import serializers

# URL/API value -> the title-cased workflow type used by the existing
# workflows / snapshot code.
PROCESS_TYPES = {
    "recruitment": "Recruitment",
    "onboarding": "Onboarding",
    "exit": "Exit",
}


class SopStepCreateSerializer(serializers.Serializer):
    who = serializers.CharField(max_length=200)
    when = serializers.CharField(max_length=500)
    how = serializers.CharField(max_length=2000)
    required = serializers.BooleanField(required=False, default=True)
    active = serializers.BooleanField(required=False, default=True)
    tat_days = serializers.IntegerField(required=False, default=1, min_value=0)


class SopStepUpdateSerializer(serializers.Serializer):
    who = serializers.CharField(max_length=200, required=False)
    when = serializers.CharField(max_length=500, required=False)
    how = serializers.CharField(max_length=2000, required=False)
    required = serializers.BooleanField(required=False)
    active = serializers.BooleanField(required=False)
    tat_days = serializers.IntegerField(required=False, min_value=0)


class SopReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
