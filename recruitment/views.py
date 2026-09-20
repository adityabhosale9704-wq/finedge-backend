from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from positions.views import assign_employee_to_position, find_or_create_vacant_position
from recruitment.mongo import get_candidates_collection, get_requisitions_collection
from recruitment.serializers import (
    CandidateCreateSerializer,
    CandidateUpdateSerializer,
    RequisitionApproveSerializer,
    RequisitionCreateSerializer,
    RequisitionUpdateSerializer,
)
from workflows.views import snapshot_steps_for_instance


def generate_next_sequential_id(collection, prefix):
    max_num = 0
    for doc in collection.find({}, {"id": 1}):
        value = doc.get("id", "")
        if value.startswith(prefix + "-"):
            try:
                max_num = max(max_num, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{max_num + 1:04d}"


def get_requisition_by_id(req_id):
    return get_requisitions_collection().find_one({"id": req_id})


def get_candidate_by_id(cand_id):
    return get_candidates_collection().find_one({"id": cand_id})


def serialize_requisition(doc):
    return {
        "id": doc["id"],
        "role": doc.get("role", ""),
        "branch": doc.get("branch", ""),
        "openings": doc.get("openings", 0),
        "raised_by": doc.get("raised_by", ""),
        "raised_date": doc.get("raised_date", ""),
        "tat_days": doc.get("tat_days", 30),
        "stage": doc.get("stage", "Open"),
        "budget": doc.get("budget", ""),
        "approved_by": doc.get("approved_by"),
        "approved_at": doc.get("approved_at"),
    }


def serialize_candidate(doc):
    requisition_id = doc.get("requisition_id")
    requisition_role = None
    requisition_branch = None
    if requisition_id:
        requisition = get_requisition_by_id(requisition_id)
        if requisition:
            requisition_role = requisition.get("role")
            requisition_branch = requisition.get("branch")

    steps = doc.get("steps", [])
    done_count = len([s for s in steps if s.get("done")])

    return {
        "id": doc["id"],
        "name": doc.get("name", ""),
        "phone": doc.get("phone", ""),
        "email": doc.get("email", ""),
        "requisition_id": requisition_id,
        "requisition_role": requisition_role,
        "requisition_branch": requisition_branch,
        "source": doc.get("source", ""),
        "experience": doc.get("experience", ""),
        "stage": doc.get("stage", "Applied"),
        "created_at": doc.get("created_at", ""),
        "steps": steps,
        "steps_done_count": done_count,
        "steps_total_count": len(steps),
    }


class RequisitionListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requisitions = get_requisitions_collection().find()
        return Response([serialize_requisition(r) for r in requisitions])

    def post(self, request):
        serializer = RequisitionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        requisition_doc = {
            "id": generate_next_sequential_id(get_requisitions_collection(), "REQ"),
            "role": data["role"],
            "branch": data["branch"],
            "openings": data["openings"],
            "raised_by": data["raised_by"],
            "raised_date": date.today().isoformat(),
            "tat_days": data.get("tat_days", 30),
            "stage": data.get("stage", "Open"),
            "budget": data.get("budget", ""),
            "approved_by": None,
            "approved_at": None,
        }
        get_requisitions_collection().insert_one(requisition_doc)
        return Response(
            serialize_requisition(requisition_doc), status=status.HTTP_201_CREATED
        )


class RequisitionDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, req_id):
        requisition = get_requisition_by_id(req_id)
        if not requisition:
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RequisitionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_requisitions_collection().update_one({"id": req_id}, {"$set": data})

        updated = get_requisition_by_id(req_id)
        return Response(serialize_requisition(updated))

    def delete(self, request, req_id):
        requisition = get_requisition_by_id(req_id)
        if not requisition:
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_requisitions_collection().delete_one({"id": req_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


class RequisitionApproveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, req_id):
        requisition = get_requisition_by_id(req_id)
        if not requisition:
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if requisition.get("approved_by"):
            return Response(
                {
                    "detail": "This requisition has already been approved by "
                    + requisition["approved_by"]
                    + "."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RequisitionApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved_by = serializer.validated_data["approved_by"]

        get_requisitions_collection().update_one(
            {"id": req_id},
            {
                "$set": {
                    "approved_by": approved_by,
                    "approved_at": timezone.now().isoformat(),
                }
            },
        )

        updated = get_requisition_by_id(req_id)
        return Response(serialize_requisition(updated))


class CandidateListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = {}
        requisition_id = request.query_params.get("requisition_id")
        if requisition_id:
            query["requisition_id"] = requisition_id

        candidates = get_candidates_collection().find(query)
        return Response([serialize_candidate(c) for c in candidates])

    def post(self, request):
        serializer = CandidateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        requisition_id = data.get("requisition_id")
        if requisition_id and not get_requisition_by_id(requisition_id):
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        candidate_doc = {
            "id": generate_next_sequential_id(get_candidates_collection(), "CAND"),
            "name": data["name"],
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "requisition_id": requisition_id,
            "source": data.get("source", ""),
            "experience": data.get("experience", ""),
            "stage": data.get("stage", "Applied"),
            "created_at": timezone.now().isoformat(),
            "steps": snapshot_steps_for_instance("Recruitment"),
        }
        get_candidates_collection().insert_one(candidate_doc)
        return Response(
            serialize_candidate(candidate_doc), status=status.HTTP_201_CREATED
        )


class CandidateDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CandidateUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        requisition_id = data.get("requisition_id")
        if requisition_id and not get_requisition_by_id(requisition_id):
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if data:
            get_candidates_collection().update_one({"id": cand_id}, {"$set": data})

        updated = get_candidate_by_id(cand_id)
        return Response(serialize_candidate(updated))

    def delete(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_candidates_collection().delete_one({"id": cand_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


def _toggle_candidate_step(cand_id, step_id, done):
    candidate = get_candidate_by_id(cand_id)
    if not candidate:
        return None, Response(
            {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
        )

    steps = candidate.get("steps", [])
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        return None, Response(
            {"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND
        )

    step["done"] = done
    step["done_date"] = date.today().isoformat() if done else None

    update = {"steps": steps}
    if done and all(s.get("done") for s in steps):
        update["stage"] = "Documents Pending"

    get_candidates_collection().update_one({"id": cand_id}, {"$set": update})
    updated = get_candidate_by_id(cand_id)
    return updated, None


class CandidateStepDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, step_id):
        updated, error = _toggle_candidate_step(cand_id, step_id, True)
        if error:
            return error
        return Response(serialize_candidate(updated))


class CandidateStepUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, step_id):
        updated, error = _toggle_candidate_step(cand_id, step_id, False)
        if error:
            return error
        return Response(serialize_candidate(updated))


class CandidateCreateEmployeeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if candidate.get("stage") != "Documents Pending":
            return Response(
                {
                    "detail": "Employee records can only be created for candidates "
                    "whose stage is 'Documents Pending'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requisition = None
        requisition_id = candidate.get("requisition_id")
        if requisition_id:
            requisition = get_requisition_by_id(requisition_id)

        designation = requisition.get("role", "") if requisition else ""
        branch = requisition.get("branch", "") if requisition else ""
        department = ""

        employee_doc = {
            "name": candidate.get("name", ""),
            "email": candidate.get("email", ""),
            "phone": candidate.get("phone", ""),
            "department": department,
            "designation": designation,
            "branch": branch,
            "date_of_joining": date.today().isoformat(),
            "ctc": 0,
            "status": "Onboarding",
            "family": [],
            "onboarding_steps": snapshot_steps_for_instance("Onboarding"),
        }
        result = get_employees_collection().insert_one(employee_doc)
        employee_doc["_id"] = result.inserted_id

        position = find_or_create_vacant_position(designation, department, branch)
        assign_employee_to_position(position, employee_doc)

        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"stage": "Joined"}}
        )

        return Response(
            {"employee_id": str(employee_doc["_id"]), "position_id": position["id"]},
            status=status.HTTP_201_CREATED,
        )
