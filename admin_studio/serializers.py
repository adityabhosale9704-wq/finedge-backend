from rest_framework import serializers


class DepartmentSerializer(serializers.Serializer):
    name = serializers.CharField()


class BranchSerializer(serializers.Serializer):
    name = serializers.CharField()
    city = serializers.CharField()
