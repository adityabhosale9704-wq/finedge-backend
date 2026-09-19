from rest_framework import serializers

REQUISITION_STAGE_CHOICES = ["Open", "Sourcing", "Interviewing", "Offer Stage", "Closed"]

CANDIDATE_STAGE_CHOICES = [
    "Applied",
    "Screening",
    "Interview",
    "Offer",
    "Documents Pending",
    "Joined",
    "Rejected",
    "Withdrawn",
]


class RequisitionCreateSerializer(serializers.Serializer):
    role = serializers.CharField()
    branch = serializers.CharField()
    openings = serializers.IntegerField(min_value=1)
    raised_by = serializers.CharField()
    tat_days = serializers.IntegerField(required=False, default=30)
    stage = serializers.ChoiceField(
        choices=REQUISITION_STAGE_CHOICES, required=False, default="Open"
    )
    budget = serializers.CharField(required=False, allow_blank=True, default="")


class RequisitionUpdateSerializer(serializers.Serializer):
    role = serializers.CharField(required=False)
    branch = serializers.CharField(required=False)
    openings = serializers.IntegerField(required=False, min_value=1)
    raised_by = serializers.CharField(required=False)
    tat_days = serializers.IntegerField(required=False)
    stage = serializers.ChoiceField(choices=REQUISITION_STAGE_CHOICES, required=False)
    budget = serializers.CharField(required=False, allow_blank=True)


class RequisitionApproveSerializer(serializers.Serializer):
    approved_by = serializers.CharField()


class CandidateCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    requisition_id = serializers.CharField(required=False, allow_null=True, default=None)
    source = serializers.CharField(required=False, allow_blank=True, default="")
    experience = serializers.CharField(required=False, allow_blank=True, default="")
    stage = serializers.ChoiceField(
        choices=CANDIDATE_STAGE_CHOICES, required=False, default="Applied"
    )


class CandidateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    requisition_id = serializers.CharField(required=False, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True)
    experience = serializers.CharField(required=False, allow_blank=True)
    stage = serializers.ChoiceField(choices=CANDIDATE_STAGE_CHOICES, required=False)
