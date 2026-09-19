import os
import uuid

from bson import ObjectId
from bson.errors import InvalidId
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from employees.serializers import (
    DocumentUpdateSerializer,
    DocumentUploadSerializer,
    EmployeeSerializer,
    FacilityItemSerializer,
    FamilyMemberSerializer,
)


def build_doc_url(request, file_path):
    if not file_path:
        return ""
    url = settings.MEDIA_URL + file_path
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def serialize_employee(doc, request=None):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if "date_of_joining" in doc and hasattr(doc["date_of_joining"], "isoformat"):
        doc["date_of_joining"] = doc["date_of_joining"].isoformat()
    if doc.get("dob") and hasattr(doc["dob"], "isoformat"):
        doc["dob"] = doc["dob"].isoformat()
    doc.setdefault("blood_group", "")
    doc.setdefault("kra_score", None)
    doc.setdefault("dob", "")
    doc.setdefault("marital_status", "")
    doc.setdefault("emergency_contact_name", "")
    doc.setdefault("emergency_contact_phone", "")
    doc.setdefault("family", [])
    doc.setdefault("pan", "")
    doc.setdefault("aadhaar", "")
    doc.setdefault("uan", "")
    doc.setdefault("esic", "")
    doc.setdefault("bank_account", "")
    doc.setdefault("pf_nomination_on_file", False)
    doc.setdefault("gratuity_nomination_on_file", False)
    doc.setdefault("policy_accepted", False)
    doc.setdefault("facilities", [])
    doc.setdefault("position_id", None)

    docs_list = doc.get("docs", [])
    doc["docs"] = [
        {**item, "file_path": build_doc_url(request, item.get("file_path", ""))}
        for item in docs_list
    ]
    doc["docs_count"] = len(docs_list)
    return doc


def normalize_date_field(data, key):
    if key in data:
        value = data[key]
        data[key] = value.isoformat() if value else ""


def get_employee_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_employees_collection().find_one({"_id": object_id})


class EmployeeListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees = get_employees_collection().find()
        return Response([serialize_employee(e, request) for e in employees])

    def post(self, request):
        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "date_of_joining")
        normalize_date_field(data, "dob")
        data["family"] = []

        result = get_employees_collection().insert_one(data)
        created = get_employees_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_employee(created, request), status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(serialize_employee(employee, request))

    def patch(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "date_of_joining")
        normalize_date_field(data, "dob")

        if data:
            get_employees_collection().update_one(
                {"_id": employee["_id"]}, {"$set": data}
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))

    def delete(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )
        get_employees_collection().delete_one({"_id": employee["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeFamilyListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = FamilyMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "dob")

        member = {
            "id": uuid.uuid4().hex,
            "relation": data["relation"],
            "name": data["name"],
            "dob": data.get("dob", ""),
        }

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$push": {"family": member}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request), status=status.HTTP_201_CREATED)


class EmployeeFamilyDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_family_member(self, employee, family_id):
        for member in employee.get("family", []):
            if member.get("id") == family_id:
                return member
        return None

    def patch(self, request, pk, family_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self.get_family_member(employee, family_id):
            return Response(
                {"detail": "Family member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FamilyMemberSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "dob")

        set_fields = {"family.$[member]." + key: value for key, value in data.items()}
        if set_fields:
            get_employees_collection().update_one(
                {"_id": employee["_id"]},
                {"$set": set_fields},
                array_filters=[{"member.id": family_id}],
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))

    def delete(self, request, pk, family_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self.get_family_member(employee, family_id):
            return Response(
                {"detail": "Family member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$pull": {"family": {"id": family_id}}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))


class EmployeeFacilityListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = FacilityItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "issued_date")

        facility = {
            "id": uuid.uuid4().hex,
            "item": data["item"],
            "issued_date": data.get("issued_date", ""),
        }

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$push": {"facilities": facility}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request), status=status.HTTP_201_CREATED)


class EmployeeFacilityDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_facility(self, employee, facility_id):
        for facility in employee.get("facilities", []):
            if facility.get("id") == facility_id:
                return facility
        return None

    def patch(self, request, pk, facility_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self.get_facility(employee, facility_id):
            return Response(
                {"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = FacilityItemSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        normalize_date_field(data, "issued_date")

        set_fields = {
            "facilities.$[facility]." + key: value for key, value in data.items()
        }
        if set_fields:
            get_employees_collection().update_one(
                {"_id": employee["_id"]},
                {"$set": set_fields},
                array_filters=[{"facility.id": facility_id}],
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))

    def delete(self, request, pk, facility_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self.get_facility(employee, facility_id):
            return Response(
                {"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$pull": {"facilities": {"id": facility_id}}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))


class EmployeeDocumentListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploaded_file = data["file"]

        safe_name = os.path.basename(uploaded_file.name)
        stored_filename = f"{uuid.uuid4().hex}_{safe_name}"
        relative_path = f"employee_docs/{pk}/{stored_filename}"
        default_storage.save(relative_path, uploaded_file)

        doc_entry = {
            "id": uuid.uuid4().hex,
            "name": data["name"],
            "doc_type": data.get("doc_type", ""),
            "status": data.get("status", "On file"),
            "file_path": relative_path,
            "uploaded_at": timezone.now().isoformat(),
        }

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$push": {"docs": doc_entry}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(
            serialize_employee(updated, request), status=status.HTTP_201_CREATED
        )


class EmployeeDocumentDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_document(self, employee, doc_id):
        for document in employee.get("docs", []):
            if document.get("id") == doc_id:
                return document
        return None

    def patch(self, request, pk, doc_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not self.get_document(employee, doc_id):
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = DocumentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        set_fields = {"docs.$[doc]." + key: value for key, value in data.items()}
        if set_fields:
            get_employees_collection().update_one(
                {"_id": employee["_id"]},
                {"$set": set_fields},
                array_filters=[{"doc.id": doc_id}],
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))

    def delete(self, request, pk, doc_id):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        document = self.get_document(employee, doc_id)
        if not document:
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )

        file_path = document.get("file_path")
        if file_path and default_storage.exists(file_path):
            default_storage.delete(file_path)

        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$pull": {"docs": {"id": doc_id}}}
        )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated, request))
