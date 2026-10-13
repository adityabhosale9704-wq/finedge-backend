import os
import uuid
from datetime import date

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
from lifecycle.audit import user_label, write_audit
from lifecycle.steps import compute_progress, normalize_steps, set_step_status
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
    doc.setdefault("source_candidate_id", None)
    doc["onboarding_steps"] = normalize_steps(doc.get("onboarding_steps", []))
    progress = compute_progress(doc["onboarding_steps"])
    doc["onboarding_progress_pct"] = progress["progress_pct"]
    doc["onboarding_current_step"] = progress["current_step"]
    doc["onboarding_all_required_completed"] = progress["all_required_completed"]
    doc.setdefault("lifecycle_stage", doc.get("status", ""))

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
        query = {}
        branch = request.query_params.get("branch")
        if branch:
            query["branch"] = branch

        # An employee in onboarding is not an employee yet: keep them out of the
        # main Employee List until activation. Onboarding screens use their own
        # endpoint; pass ?include_onboarding=1 to see everyone.
        if request.query_params.get("include_onboarding") != "1":
            query["status"] = {"$ne": "Onboarding"}

        employees = get_employees_collection().find(query)
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

        transition = None
        if data.get("policy_accepted") and not employee.get("policy_accepted"):
            # Accepting the policy can be the last missing onboarding condition.
            from lifecycle.transitions import evaluate_onboarding_completion

            transition = evaluate_onboarding_completion(str(employee["_id"]), request)

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        payload = serialize_employee(updated, request)
        if transition:
            payload["transition"] = transition
        return Response(payload)

    def delete(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Deferred import: positions.views imports get_employee_by_pk from this
        # module, so importing it back at module load time would be circular.
        from positions.views import unassign_position_for_employee

        unassign_position_for_employee(str(employee["_id"]))
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


class EmployeeOnboardingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees = get_employees_collection().find({"status": "Onboarding"})
        return Response([serialize_employee(e, request) for e in employees])


def _apply_onboarding_step_status(request, pk, step_id, new_status, notes=None):
    from lifecycle.transitions import evaluate_onboarding_completion

    employee = get_employee_by_pk(pk)
    if not employee:
        return None, None, Response(
            {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if employee.get("status") != "Onboarding":
        return None, None, Response(
            {"detail": "Onboarding is already complete for this employee; its history is read-only."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    steps = normalize_steps(employee.get("onboarding_steps", []))
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        return None, None, Response(
            {"detail": "Onboarding step not found."}, status=status.HTTP_404_NOT_FOUND
        )

    previous = set_step_status(step, new_status, user_label(request), notes)
    get_employees_collection().update_one(
        {"_id": employee["_id"]}, {"$set": {"onboarding_steps": steps}}
    )
    if previous != new_status:
        write_audit(
            "employee", str(employee["_id"]), "onboarding_step_status_changed",
            previous, new_status, request,
            {"step_no": step.get("step_no"), "step": step.get("how") or step.get("step_name", "")},
        )

    transition = evaluate_onboarding_completion(str(employee["_id"]), request)
    updated = get_employees_collection().find_one({"_id": employee["_id"]})
    return updated, transition, None


def _onboarding_step_response(request, pk, step_id, new_status, notes=None):
    updated, transition, error = _apply_onboarding_step_status(
        request, pk, step_id, new_status, notes
    )
    if error:
        return error
    payload = serialize_employee(updated, request)
    payload["transition"] = transition
    return Response(payload)


class EmployeeOnboardingStepDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, step_id):
        return _onboarding_step_response(request, pk, step_id, "Completed")


class EmployeeOnboardingStepUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, step_id):
        return _onboarding_step_response(request, pk, step_id, "Pending")


class EmployeeOnboardingStepStatusView(APIView):
    """POST {status: Pending | In Progress | Completed, notes?}"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, step_id):
        from recruitment.serializers import StepStatusSerializer

        serializer = StepStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return _onboarding_step_response(request, pk, step_id, data["status"], data.get("notes"))


class EmployeeCompleteOnboardingView(APIView):
    """Manual trigger kept for older screens. Onboarding now completes
    automatically; this endpoint just re-runs the same validated engine."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from lifecycle.transitions import evaluate_onboarding_completion

        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        transition = evaluate_onboarding_completion(pk, request)
        if not transition.get("moved"):
            return Response(
                {"detail": transition.get("reason", "Onboarding cannot be completed yet.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        payload = serialize_employee(updated, request)
        payload["transition"] = transition
        return Response(payload)
