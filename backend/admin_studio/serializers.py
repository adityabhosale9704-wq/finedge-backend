from rest_framework import serializers


class DepartmentSerializer(serializers.Serializer):
    name = serializers.CharField()


class BranchSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True, default="")
    manager_name = serializers.CharField(required=False, allow_blank=True, default="")
    s_and_e_number = serializers.CharField(required=False, allow_blank=True, default="")


class BranchUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    state = serializers.CharField(required=False, allow_blank=True)
    manager_name = serializers.CharField(required=False, allow_blank=True)
    s_and_e_number = serializers.CharField(required=False, allow_blank=True)
    # code is deliberately not accepted here — it is permanent once a branch
    # is created (matches the user manual: "Once saved this cannot be changed").


class RoleSerializer(serializers.Serializer):
    title = serializers.CharField()
    job_description = serializers.CharField(required=False, allow_blank=True, default="")
