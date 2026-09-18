from rest_framework import serializers


class EmployeeSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    department = serializers.CharField()
    designation = serializers.CharField()
    branch = serializers.CharField()
    date_of_joining = serializers.DateField()
    ctc = serializers.FloatField()
    status = serializers.CharField()
