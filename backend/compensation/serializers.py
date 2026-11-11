from rest_framework import serializers

REVISION_STATUS_CHOICES = ["Pending", "Approved", "Rejected"]


class SalaryStructureSerializer(serializers.Serializer):
    basic_pct = serializers.FloatField(required=False)
    hra_pct_metro = serializers.FloatField(required=False)
    hra_pct_nonmetro = serializers.FloatField(required=False)
    pf_cap_monthly = serializers.FloatField(required=False)
    gratuity_pct = serializers.FloatField(required=False)
    esi_limit_monthly = serializers.FloatField(required=False)
    professional_tax_monthly = serializers.FloatField(required=False)


class SalaryRevisionCreateSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    current_ctc = serializers.FloatField()
    proposed_ctc = serializers.FloatField()
    effective_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class SalaryRevisionApproveSerializer(serializers.Serializer):
    # No body fields required; kept as a serializer for symmetry with the
    # rest of this app's approve-style endpoints.
    pass
