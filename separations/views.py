from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from employees.views import get_employee_by_pk
from positions.views import unassign_position_for_employee
from separations.mongo import get_separations_collection
from separations.serializers import SeparationCreateSerializer, SeparationUpdateSerializer
from workflows.views import snapshot_steps_for_instance


def generate_next_separation_id():
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


def serialize_separation(doc):
    employee = get_employee_by_pk(doc.get("employee_id", ""))
    steps = doc.get("steps", [])
    done_count = len([s for s in steps if s.get("done")])

    return {
        "id": doc["id"],
        "employee_id": doc.get("employee_id", ""),
        "employee_name": employee.get("name", "") if employee else "",
        "resignation_date": doc.get("resignation_date", ""),
        "last_working_day": doc.get("last_working_day", ""),
        "notice_period_days": doc.get("notice_period_days", 30),
        "reason": doc.get("reason", ""),
        "steps": steps,
        "steps_done_count": done_count,
        "steps_total_count": len(steps),
        "is_complete": len(steps) > 0 and done_count == len(steps),
        "relieving_letter_status": doc.get("relieving_letter_status", "Pending"),
        "full_final_settlement_note": doc.get("full_final_settlement_note", ""),
    }


class SeparationListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        separations = get_separations_collection().find()
        return Response([serialize_separation(s) for s in separations])

    def post(self, request):
        serializer = SeparationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee = get_employee_by_pk(data["employee_id"])
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        existing = get_separations_collection().find_one(
            {"employee_id": data["employee_id"]}
        )
        if existing and not (
            existing.get("steps")
            and all(s.get("done") for s in existing.get("steps", []))
        ):
            return Response(
                {"detail": "This employee already has a separation in progress."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        separation_doc = {
            "id": generate_next_separation_id(),
            "employee_id": data["employee_id"],
            "resignation_date": data["resignation_date"].isoformat(),
            "last_working_day": data["last_working_day"].isoformat(),
            "notice_period_days": data.get("notice_period_days", 30),
            "reason": data.get("reason", ""),
            "steps": snapshot_steps_for_instance("Exit"),
            "relieving_letter_status": "Pending",
            "full_final_settlement_note": "",
            "created_at": timezone.now().isoformat(),
        }
        get_separations_collection().insert_one(separation_doc)
        return Response(
            serialize_separation(separation_doc), status=status.HTTP_201_CREATED
        )


class SeparationDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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

        updated = get_separation_by_id(sep_id)
        return Response(serialize_separation(updated))


def _toggle_separation_step(sep_id, step_id, done):
    separation = get_separation_by_id(sep_id)
    if not separation:
        return None, Response(
            {"detail": "Separation not found."}, status=status.HTTP_404_NOT_FOUND
        )

    steps = separation.get("steps", [])
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        return None, Response(
            {"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND
        )

    step["done"] = done
    step["done_date"] = date.today().isoformat() if done else None

    get_separations_collection().update_one(
        {"id": sep_id}, {"$set": {"steps": steps}}
    )

    if done and all(s.get("done") for s in steps):
        employee = get_employee_by_pk(separation["employee_id"])
        if employee:
            get_employees_collection().update_one(
                {"_id": employee["_id"]}, {"$set": {"status": "Leaver"}}
            )
            unassign_position_for_employee(separation["employee_id"])

    updated = get_separation_by_id(sep_id)
    return updated, None


class SeparationStepDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, sep_id, step_id):
        updated, error = _toggle_separation_step(sep_id, step_id, True)
        if error:
            return error
        return Response(serialize_separation(updated))


class SeparationStepUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, sep_id, step_id):
        updated, error = _toggle_separation_step(sep_id, step_id, False)
        if error:
            return error
        return Response(serialize_separation(updated))
