from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import get_employees_collection, get_separations_collection
from database.queries import get_employee_by_pk
from lifecycle.audit import write_audit
from lifecycle.steps import compute_progress, normalize_steps
from recruitment.serializers import StepStatusSerializer
from separations.serializers import (
    InitiateExitSerializer,
    SeparationCreateSerializer,
    SeparationUpdateSerializer,
)
from separations.services import (
    apply_separation_step_status,
    create_separation,
    get_separation_by_id,
    separation_is_complete,
)

EXIT_INITIATED_MESSAGE = "Exit process initiated successfully."


def build_employee_lookup(employee_ids):
    """One batched query for name / department / designation / employee id."""
    object_ids = []
    for employee_id in employee_ids:
        try:
            object_ids.append(ObjectId(employee_id))
        except (InvalidId, TypeError):
            continue
    if not object_ids:
        return {}
    employees = get_employees_collection().find({"_id": {"$in": object_ids}})
    return {str(e["_id"]): e for e in employees}


def serialize_separation(doc, employee_lookup=None):
    employee_id = doc.get("employee_id", "")
    if employee_lookup is not None:
        employee = employee_lookup.get(employee_id)
    else:
        employee = get_employee_by_pk(employee_id)
    employee = employee or {}

    steps = normalize_steps(doc.get("steps", []))
    progress = compute_progress(steps)
    complete = separation_is_complete(doc)

    return {
        "id": doc["id"],
        "employee_id": employee_id,
        "employee_name": employee.get("name", ""),
        "employee_code": employee.get("position_id") or "",
        "department": employee.get("department", ""),
        "designation": employee.get("designation", ""),
        "resignation_date": doc.get("resignation_date", ""),
        "last_working_day": doc.get("last_working_day", ""),
        "notice_period_days": doc.get("notice_period_days", 30),
        "reason": doc.get("reason", ""),
        "status": "Completed" if complete else "In Progress",
        "completed_at": doc.get("completed_at"),
        "initiated_by": doc.get("initiated_by", ""),
        "steps": steps,
        "steps_done_count": progress["steps_done_count"],
        "steps_total_count": progress["steps_total_count"],
        "progress_pct": progress["progress_pct"],
        "current_step": progress["current_step"],
        "pending_tasks": progress["pending_tasks"],
        "is_complete": complete,
        "relieving_letter_status": doc.get("relieving_letter_status", "Pending"),
        "full_final_settlement_note": doc.get("full_final_settlement_note", ""),
    }


class SeparationListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        separations = list(get_separations_collection().find())

        branch = request.query_params.get("branch")
        if branch:
            branch_employee_ids = {
                str(e["_id"]) for e in get_employees_collection().find({"branch": branch}, {"_id": 1})
            }
            separations = [s for s in separations if s.get("employee_id") in branch_employee_ids]

        employee_lookup = build_employee_lookup(
            s.get("employee_id") for s in separations if s.get("employee_id")
        )
        return Response([serialize_separation(s, employee_lookup) for s in separations])

    def post(self, request):
        serializer = SeparationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee = get_employee_by_pk(data["employee_id"])
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        doc = create_separation(
            request, employee, data["resignation_date"], data["last_working_day"],
            data.get("reason", ""), data.get("notice_period_days", 30),
        )
        return Response(
            {**serialize_separation(doc), "message": EXIT_INITIATED_MESSAGE},
            status=status.HTTP_201_CREATED,
        )


class InitiateExitView(APIView):
    """POST /employees/<pk>/initiate-exit/ {resignation_date, last_working_day, reason}

    Creates ONE exit record and snapshots the Exit SOP. It does NOT delete the
    employee or change their status: that only happens when the exit completes.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        employee = get_employee_by_pk(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = InitiateExitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        doc = create_separation(
            request, employee, data["resignation_date"], data["last_working_day"],
            data.get("reason", ""),
        )
        return Response(
            {**serialize_separation(doc), "message": EXIT_INITIATED_MESSAGE},
            status=status.HTTP_201_CREATED,
        )


class SeparationDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, sep_id):
        separation = get_separation_by_id(sep_id)
        if not separation:
            return Response(
                {"detail": "Separation not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(serialize_separation(separation))

    def patch(self, request, sep_id):
        separation = get_separation_by_id(sep_id)
        if not separation:
            return Response(
                {"detail": "Separation not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = SeparationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_separations_collection().update_one({"id": sep_id}, {"$set": data})
            write_audit("separation", sep_id, "details_updated", None, None, request, data)

        updated = get_separation_by_id(sep_id)
        return Response(serialize_separation(updated))

    def delete(self, request, sep_id):
        separation = get_separation_by_id(sep_id)
        if not separation:
            return Response(
                {"detail": "Separation not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_separations_collection().delete_one({"id": sep_id})
        write_audit("separation", sep_id, "separation_deleted", None, None, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _step_response(request, sep_id, step_id, new_status, notes=None):
    updated, transition = apply_separation_step_status(
        request, sep_id, step_id, new_status, notes
    )
    return Response({**serialize_separation(updated), "transition": transition})


class SeparationStepDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, sep_id, step_id):
        return _step_response(request, sep_id, step_id, "Completed")


class SeparationStepUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, sep_id, step_id):
        return _step_response(request, sep_id, step_id, "Pending")


class SeparationStepStatusView(APIView):
    """POST {status: Pending | In Progress | Completed, notes?}"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, sep_id, step_id):
        serializer = StepStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return _step_response(request, sep_id, step_id, data["status"], data.get("notes"))
