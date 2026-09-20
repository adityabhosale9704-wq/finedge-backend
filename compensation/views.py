from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from compensation.mongo import (
    get_salary_revisions_collection,
    get_salary_structure_collection,
)
from compensation.serializers import (
    SalaryRevisionCreateSerializer,
    SalaryStructureSerializer,
)
from employees.views import get_employee_by_pk

DEFAULT_SALARY_STRUCTURE = {
    "basic_pct": 50,
    "hra_pct_metro": 50,
    "hra_pct_nonmetro": 40,
    "pf_cap_monthly": 1800,
    "gratuity_pct": 4.81,
    "esi_limit_monthly": 21000,
    "professional_tax_monthly": 200,
}


def get_or_create_salary_structure():
    collection = get_salary_structure_collection()
    doc = collection.find_one({"key": "singleton"})
    if doc:
        return doc

    doc = {"key": "singleton"}
    doc.update(DEFAULT_SALARY_STRUCTURE)
    collection.insert_one(doc)
    return doc


def serialize_salary_structure(doc):
    return {
        "basic_pct": doc.get("basic_pct", DEFAULT_SALARY_STRUCTURE["basic_pct"]),
        "hra_pct_metro": doc.get("hra_pct_metro", DEFAULT_SALARY_STRUCTURE["hra_pct_metro"]),
        "hra_pct_nonmetro": doc.get(
            "hra_pct_nonmetro", DEFAULT_SALARY_STRUCTURE["hra_pct_nonmetro"]
        ),
        "pf_cap_monthly": doc.get("pf_cap_monthly", DEFAULT_SALARY_STRUCTURE["pf_cap_monthly"]),
        "gratuity_pct": doc.get("gratuity_pct", DEFAULT_SALARY_STRUCTURE["gratuity_pct"]),
        "esi_limit_monthly": doc.get(
            "esi_limit_monthly", DEFAULT_SALARY_STRUCTURE["esi_limit_monthly"]
        ),
        "professional_tax_monthly": doc.get(
            "professional_tax_monthly", DEFAULT_SALARY_STRUCTURE["professional_tax_monthly"]
        ),
    }


class SalaryStructureView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doc = get_or_create_salary_structure()
        return Response(serialize_salary_structure(doc))

    def patch(self, request):
        get_or_create_salary_structure()

        serializer = SalaryStructureSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_salary_structure_collection().update_one(
                {"key": "singleton"}, {"$set": data}
            )

        updated = get_or_create_salary_structure()
        return Response(serialize_salary_structure(updated))


def generate_next_revision_id():
    max_num = 0
    for doc in get_salary_revisions_collection().find({}, {"id": 1}):
        value = doc.get("id", "")
        if value.startswith("REV-"):
            try:
                max_num = max(max_num, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"REV-{max_num + 1:04d}"


def get_revision_by_id(rev_id):
    return get_salary_revisions_collection().find_one({"id": rev_id})


def serialize_revision(doc):
    employee = get_employee_by_pk(doc.get("employee_id", ""))
    return {
        "id": doc["id"],
        "employee_id": doc.get("employee_id", ""),
        "employee_name": employee.get("name", "") if employee else "",
        "current_ctc": doc.get("current_ctc", 0),
        "proposed_ctc": doc.get("proposed_ctc", 0),
        "effective_date": doc.get("effective_date", ""),
        "reason": doc.get("reason", ""),
        "status": doc.get("status", "Pending"),
        "created_at": doc.get("created_at", ""),
    }


class SalaryRevisionListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        revisions = get_salary_revisions_collection().find()
        return Response([serialize_revision(r) for r in revisions])

    def post(self, request):
        serializer = SalaryRevisionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee = get_employee_by_pk(data["employee_id"])
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        revision_doc = {
            "id": generate_next_revision_id(),
            "employee_id": data["employee_id"],
            "current_ctc": data["current_ctc"],
            "proposed_ctc": data["proposed_ctc"],
            "effective_date": data["effective_date"].isoformat(),
            "reason": data.get("reason", ""),
            "status": "Pending",
            "created_at": timezone.now().isoformat(),
        }
        get_salary_revisions_collection().insert_one(revision_doc)
        return Response(serialize_revision(revision_doc), status=status.HTTP_201_CREATED)


class SalaryRevisionApproveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, rev_id):
        revision = get_revision_by_id(rev_id)
        if not revision:
            return Response(
                {"detail": "Salary revision not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if revision.get("status") != "Pending":
            return Response(
                {"detail": "Only pending revisions can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        get_salary_revisions_collection().update_one(
            {"id": rev_id}, {"$set": {"status": "Approved"}}
        )
        updated = get_revision_by_id(rev_id)
        return Response(serialize_revision(updated))


class SalaryRevisionRejectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, rev_id):
        revision = get_revision_by_id(rev_id)
        if not revision:
            return Response(
                {"detail": "Salary revision not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if revision.get("status") != "Pending":
            return Response(
                {"detail": "Only pending revisions can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        get_salary_revisions_collection().update_one(
            {"id": rev_id}, {"$set": {"status": "Rejected"}}
        )
        updated = get_revision_by_id(rev_id)
        return Response(serialize_revision(updated))
