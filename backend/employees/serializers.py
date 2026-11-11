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
    blood_group = serializers.CharField(
        max_length=5, required=False, allow_blank=True, default=""
    )
    kra_score = serializers.IntegerField(required=False, allow_null=True, default=None)
    dob = serializers.DateField(required=False, allow_null=True, default=None)
    marital_status = serializers.CharField(required=False, allow_blank=True, default="")
    emergency_contact_name = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    emergency_contact_phone = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    pan = serializers.CharField(required=False, allow_blank=True, default="")
    aadhaar = serializers.CharField(required=False, allow_blank=True, default="")
    uan = serializers.CharField(required=False, allow_blank=True, default="")
    esic = serializers.CharField(required=False, allow_blank=True, default="")
    bank_account = serializers.CharField(required=False, allow_blank=True, default="")
    pf_nomination_on_file = serializers.BooleanField(required=False, default=False)
    gratuity_nomination_on_file = serializers.BooleanField(required=False, default=False)
    policy_accepted = serializers.BooleanField(required=False, default=False)


class FamilyMemberSerializer(serializers.Serializer):
    relation = serializers.CharField()
    name = serializers.CharField()
    dob = serializers.DateField(required=False, allow_null=True, default=None)


class FacilityItemSerializer(serializers.Serializer):
    item = serializers.CharField()
    issued_date = serializers.DateField(required=False, allow_null=True, default=None)


DOCUMENT_STATUS_CHOICES = ["Pending verification", "Verified", "On file"]


class DocumentUploadSerializer(serializers.Serializer):
    name = serializers.CharField()
    doc_type = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=DOCUMENT_STATUS_CHOICES, required=False, default="On file"
    )
    file = serializers.FileField()


class DocumentUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    doc_type = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=DOCUMENT_STATUS_CHOICES, required=False)
