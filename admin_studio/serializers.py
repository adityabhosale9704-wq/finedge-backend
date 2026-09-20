from rest_framework import serializers


class DepartmentSerializer(serializers.Serializer):
    name = serializers.CharField()


class BranchSerializer(serializers.Serializer):
    name = serializers.CharField()
    city = serializers.CharField()
    s_and_e_number = serializers.CharField(required=False, allow_blank=True, default="")


class RoleSerializer(serializers.Serializer):
    title = serializers.CharField()
    job_description = serializers.CharField(required=False, allow_blank=True, default="")
