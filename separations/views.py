from bson import ObjectId
from bson.errors import InvalidId
from django.utils import timezone
from pymongo.errors import DuplicateKeyError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from accounts.rbac import require_hr_admin
from employees.mongo import get_employees_collection
from employees.views import get_employee_by_pk
from lifecycle.audit import user_label, write_audit
from lifecycle.steps import compute_progress, normalize_steps, set_step_status
from positions.views import unassign_position_for_employee
from recruitment.serializers import StepStatusSerializer
from separations.mongo import get_separations_collection
from separations.serializers import (
    InitiateExitSerializer,
    SeparationCreateSerializer,
    SeparationUpdateSerializer,
)
from workflows.views import snapshot_steps_for_instance

EXIT_INITIATED_MESSAGE = "Exit process initiated successfully."
EXIT_COMPLETED_MESSAGE = "Exit & Separation process completed."


def generate_next_separation_id():
    # NOTE: scans for the highest number and adds 1 (same approach as the other
    # sequential ids). Two simultaneous creations could pick the same number;
    # the unique index on separations.id (scripts/create_indexes.py) turns that
    # into a rejected insert instead of a silent duplicate.
    max_num = 0
    for doc in get_separations_collection().find({}, {"id": 1}):
        value = doc.get("id", "")
        if value.startswith("SEP-"):
            try:
                max_num = max(max_num, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"SEP-{max_num + 1:04d}"


def get_separation_by_id(sep_id):
    return get_separations_collection().find_one({"id": sep_id})


def separation_is_complete(doc):
    if doc.get("status"):
        return doc["status"] == "Completed"
    # Older records have no `status`: derive it from their steps.
    steps = doc.get("steps", [])
    return len(steps) > 0 and all(s.get("done") for s in steps)


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


def open_separation_for(employee_id):
    for doc in get_separations_collection().find({"employee_id": employee_id}):
        if separation_is_complete(doc):
            continue
        return doc
    return None


def create_separation(request, employee, resignation_date, last_working_day, reason, notice_period_days=None):
    """Shared by the Employee List 'Initiate Exit Process' action and the older
    'New Separation' form. Returns (separation_doc, error_response)."""
    require_hr_admin(request)
    employee_id = str(employee["_id"])

    if str(employee.get("status", "")).lower() in ("leaver", "onboarding"):
        return None, Response(
            {"detail": "An exit can only be initiated for a current employee (this one is "
             + str(employee.get("status", "")) + ")."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if open_separation_for(employee_id):
        return None, Response(
            {"detail": "This employee already has an exit process in progress."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if notice_period_days is None:
        notice_period_days = max((last_working_day - resignation_date).days, 0)

    separation_doc = {
        "id": generate_next_separation_id(),
        "employee_id": employee_id,
        "resignation_date": resignation_date.isoformat(),
        "last_working_day": last_working_day.isoformat(),
        "notice_period_days": notice_period_days,
        "reason": reason,
        "status": "In Progress",
        "initiated_by": user_label(request),
        "steps": snapshot_steps_for_instance("Exit"),
        "relieving_letter_status": "Pending",
        "full_final_settlement_note": "",
        "created_at": timezone.now().isoformat(),
    }
    try:
        get_separations_collection().insert_one(separation_doc)
    except DuplicateKeyError:
        # The partial unique index caught a simultaneous second initiation.
        return None, Response(
            {"detail": "This employee already has an exit process in progress."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    write_audit(
        "separation", separation_doc["id"], "exit_initiated", None, "In Progress", request,
        {"employee_id": employee_id, "last_working_day": separation_doc["last_working_day"]},
    )
    write_audit(
        "employee", employee_id, "exit_initiated", None, separation_doc["id"], request,
        {"resignation_date": separation_doc["resignation_date"], "reason": reason},
    )
    return separation_doc, None


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

        doc, error = create_separation(
            request, employee, data["resignation_date"], data["last_working_day"],
            data.get("reason", ""), data.get("notice_period_days", 30),
        )
        if error:
            return error
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

        doc, error = create_separation(
            request, employee, data["resignation_date"], data["last_working_day"],
            data.get("reason", ""),
        )
        if error:
            return error
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


def _apply_separation_step_status(request, sep_id, step_id, new_status, notes=None):
    separation = get_separation_by_id(sep_id)
    if not separation:
        return None, None, Response(
            {"detail": "Separation not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if separation.get("status") == "Completed":
        return None, None, Response(
            {"detail": "This exit process is completed; its history is read-only."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    steps = normalize_steps(separation.get("steps", []))
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        return None, None, Response(
            {"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND
        )

    previous = set_step_status(step, new_status, user_label(request), notes)
    get_separations_collection().update_one({"id": sep_id}, {"$set": {"steps": steps}})
    if previous != new_status:
        write_audit(
            "separation", sep_id, "step_status_changed", previous, new_status, request,
            {"step_no": step.get("step_no"), "step": step.get("how") or step.get("step_name", "")},
        )

    transition = None
    if compute_progress(steps)["all_required_completed"]:
        # Conditional update: only the first caller completes the exit.
        result = get_separations_collection().update_one(
            {"id": sep_id, "status": {"$ne": "Completed"}},
            {"$set": {"status": "Completed", "completed_at": timezone.now().isoformat()}},
        )
        if result.modified_count == 1:
            employee = get_employee_by_pk(separation["employee_id"])
            if employee:
                previous_employee_status = employee.get("status")
                get_employees_collection().update_one(
                    {"_id": employee["_id"]},
                    {"$set": {"status": "Leaver", "lifecycle_stage": "Leaver"}},
                )
                unassign_position_for_employee(separation["employee_id"])
                write_audit(
                    "employee", str(employee["_id"]), "stage_transition",
                    previous_employee_status, "Leaver", request, {"separation_id": sep_id},
                )
            write_audit(
                "separation", sep_id, "exit_completed", "In Progress", "Completed", request,
            )
            transition = {"moved": True, "message": EXIT_COMPLETED_MESSAGE}

    return get_separation_by_id(sep_id), transition, None


def _step_response(request, sep_id, step_id, new_status, notes=None):
    updated, transition, error = _apply_separation_step_status(
        request, sep_id, step_id, new_status, notes
    )
    if error:
        return error
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
