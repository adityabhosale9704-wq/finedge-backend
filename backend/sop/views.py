import uuid

from django.utils import timezone
from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from accounts.rbac import require_hr_admin
from database.collections import get_sop_templates_collection
from lifecycle.audit import write_audit
from sop.serializers import (
    PROCESS_TYPES,
    SopReorderSerializer,
    SopStepCreateSerializer,
    SopStepUpdateSerializer,
)
from sop.service import list_steps

# Temporary step_no values used while renumbering. They sit far above any real
# step number so the unique (process_type, step_no) index is never violated
# part-way through a renumber.
TEMP_OFFSET = 100000


def serialize_step(doc):
    return {
        "id": doc["id"],
        "process_type": doc["process_type"],
        "step_no": doc["step_no"],
        "who": doc.get("who", ""),
        "when": doc.get("when", ""),
        "how": doc.get("how", ""),
        "required": doc.get("required", True),
        "active": doc.get("active", True),
        "tat_days": doc.get("tat_days", 1),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def serialize_steps(process_type):
    return [serialize_step(d) for d in list_steps(process_type)]


def invalid_process_type():
    return Response(
        {"detail": "Invalid process_type. Use recruitment, onboarding or exit."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def resequence(process_type, ordered_ids):
    """Give the steps step_no 1..N in the order of ordered_ids.

    Done as ONE ordered bulk_write in two passes (temp numbers, then final
    numbers): a single round trip, and the unique index is never hit mid-way.
    If the process died between the passes the order would still be intact
    (temp numbers preserve it) and the next resequence heals it.
    """
    now = timezone.now().isoformat()
    operations = []
    for index, step_id in enumerate(ordered_ids):
        operations.append(
            UpdateOne(
                {"id": step_id, "process_type": process_type},
                {"$set": {"step_no": TEMP_OFFSET + index + 1}},
            )
        )
    for index, step_id in enumerate(ordered_ids):
        operations.append(
            UpdateOne(
                {"id": step_id, "process_type": process_type},
                {"$set": {"step_no": index + 1, "updated_at": now}},
            )
        )
    if operations:
        get_sop_templates_collection().bulk_write(operations, ordered=True)


class SopStepListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, process_type):
        if process_type not in PROCESS_TYPES:
            return invalid_process_type()
        return Response(serialize_steps(process_type))

    def post(self, request, process_type):
        if process_type not in PROCESS_TYPES:
            return invalid_process_type()
        require_hr_admin(request)

        serializer = SopStepCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        collection = get_sop_templates_collection()
        list_steps(process_type)  # makes sure first-use seeding has happened
        now = timezone.now().isoformat()

        # Two admins adding at the same moment would compute the same step_no;
        # the unique index rejects the loser, who simply retries with a fresh max.
        for _ in range(5):
            last = collection.find_one(
                {"process_type": process_type}, sort=[("step_no", -1)]
            )
            next_no = (last["step_no"] if last else 0) + 1
            doc = {
                "id": uuid.uuid4().hex,
                "process_type": process_type,
                "step_no": next_no,
                "who": data["who"],
                "when": data["when"],
                "how": data["how"],
                "required": data["required"],
                "active": data["active"],
                "tat_days": data["tat_days"],
                "created_at": now,
                "updated_at": now,
            }
            try:
                collection.insert_one(doc)
                break
            except DuplicateKeyError:
                continue
        else:
            return Response(
                {"detail": "Could not add the step right now. Please try again."},
                status=status.HTTP_409_CONFLICT,
            )

        write_audit(
            "sop", process_type, "sop_edited", None, "step added", request,
            {"step_no": doc["step_no"], "who": doc["who"], "how": doc["how"]},
        )
        return Response(serialize_steps(process_type), status=status.HTTP_201_CREATED)


class SopStepDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, step_id):
        require_hr_admin(request)
        collection = get_sop_templates_collection()
        step = collection.find_one({"id": step_id})
        if not step:
            return Response({"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SopStepUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            data["updated_at"] = timezone.now().isoformat()
            collection.update_one({"id": step_id}, {"$set": data})
            changes = {k: v for k, v in data.items() if k != "updated_at"}
            write_audit(
                "sop", step["process_type"], "sop_edited", None, "step updated", request,
                {"step_no": step["step_no"], "changes": changes},
            )

        return Response(serialize_steps(step["process_type"]))

    def delete(self, request, step_id):
        require_hr_admin(request)
        collection = get_sop_templates_collection()
        step = collection.find_one({"id": step_id})
        if not step:
            return Response({"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND)

        process_type = step["process_type"]
        collection.delete_one({"id": step_id})

        remaining = [
            d["id"]
            for d in collection.find({"process_type": process_type}, {"id": 1}).sort("step_no", 1)
        ]
        resequence(process_type, remaining)
        write_audit(
            "sop", process_type, "sop_edited", None, "step deleted", request,
            {"step_no": step["step_no"], "who": step.get("who"), "how": step.get("how")},
        )
        return Response(serialize_steps(process_type))


class SopStepReorderView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, process_type):
        if process_type not in PROCESS_TYPES:
            return invalid_process_type()
        require_hr_admin(request)

        serializer = SopReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ordered_ids = serializer.validated_data["ordered_ids"]

        current_ids = [
            d["id"]
            for d in get_sop_templates_collection().find(
                {"process_type": process_type}, {"id": 1}
            )
        ]
        if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(current_ids):
            return Response(
                {"detail": "ordered_ids must list every step of this process exactly once. Refresh and try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resequence(process_type, ordered_ids)
        write_audit("sop", process_type, "sop_edited", None, "steps reordered", request)
        return Response(serialize_steps(process_type))
