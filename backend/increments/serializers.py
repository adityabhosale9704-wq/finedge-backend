from rest_framework import serializers


class SlabSerializer(serializers.Serializer):
    disbursement_min = serializers.FloatField()
    disbursement_max = serializers.FloatField()
    payout_pct = serializers.FloatField()


class IncentiveStructureCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    department = serializers.CharField(required=False, allow_blank=True, default="")
    slabs = SlabSerializer(many=True, required=False, default=list)
    bonus_threshold = serializers.FloatField(required=False, default=0)
    bonus_amount = serializers.FloatField(required=False, default=0)


class IncentiveStructureUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    department = serializers.CharField(required=False, allow_blank=True)
    slabs = SlabSerializer(many=True, required=False)
    bonus_threshold = serializers.FloatField(required=False)
    bonus_amount = serializers.FloatField(required=False)
