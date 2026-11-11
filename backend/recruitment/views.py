from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import (
    get_candidates_collection,
    get_reference_checks_collection,
    get_requisitions_collection,
)
from database.queries import generate_next_sequential_id, get_candidate_by_id, get_requisition_by_id
from lifecycle.audit import write_audit
from lifecycle.steps import compute_progress, normalize_steps
from lifecycle.transitions import (
    candidate_transition_status,
    evaluate_candidate_transition,
    move_candidate_to_onboarding,
)
from recruitment.serializers import (
    CandidateCreateSerializer,
    CandidateOutcomeSerializer,
    CandidateUpdateSerializer,
    RequisitionApproveSerializer,
    RequisitionCreateSerializer,
    RequisitionUpdateSerializer,
    StepStatusSerializer,
)
from recruitment.services import apply_candidate_step_status
from workflows.services import snapshot_steps_for_instance


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


def build_requisition_lookup(requisition_ids):
    """One batched query instead of one lookup per candidate row."""
    ids = [r for r in requisition_ids if r]
    if not ids:
        return {}
    requisitions = get_requisitions_collection().find({"id": {"$in": ids}})
    return {r["id"]: r for r in requisitions}


def serialize_candidate(doc, requisition_lookup=None, transition=None):
    requisition_id = doc.get("requisition_id")
    requisition_role = None
    requisition_branch = None
    if requisition_id:
        if requisition_lookup is not None:
            requisition = requisition_lookup.get(requisition_id)
        else:
            requisition = get_requisition_by_id(requisition_id)
        if requisition:
            requisition_role = requisition.get("role")
            requisition_branch = requisition.get("branch")

    steps = normalize_steps(doc.get("steps", []))
    progress = compute_progress(steps)
    done_count = progress["steps_done_count"]
    ready, blocked_reason = candidate_transition_status(doc)

    return {
        "id": doc["id"],
        "name": doc.get("name", ""),
        "phone": doc.get("phone", ""),
        "email": doc.get("email", ""),
        "outcome": doc.get("outcome"),
        "progress_pct": progress["progress_pct"],
        "current_step": progress["current_step"],
        "all_required_completed": progress["all_required_completed"],
        "ready_for_onboarding": ready,
        "onboarding_blocked_reason": "" if ready else blocked_reason,
        "onboarding_employee_id": doc.get("onboarding_employee_id"),
        "lifecycle_status": doc.get("lifecycle_status", ""),
        "transition": transition,
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
        "frozen": doc.get("frozen", False),
        "frozen_reason": doc.get("frozen_reason", ""),
        "doc_checklist": doc.get("doc_checklist", []),
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

        linked_count = get_candidates_collection().count_documents(
            {"requisition_id": req_id}
        )
        if linked_count:
            return Response(
                {
                    "detail": f"This requisition has {linked_count} candidate(s) linked "
                    "to it. Move or remove them before deleting the requisition."
                },
                status=status.HTTP_400_BAD_REQUEST,
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

        candidates = list(get_candidates_collection().find(query))
        requisition_lookup = build_requisition_lookup(
            c.get("requisition_id") for c in candidates
        )
        return Response(
            [serialize_candidate(c, requisition_lookup) for c in candidates]
        )

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
        write_audit(
            "candidate", candidate_doc["id"], "candidate_created",
            None, candidate_doc["stage"], request,
            {"sop_steps_snapshotted": len(candidate_doc["steps"])},
        )
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

        new_stage = data.get("stage")
        if new_stage and new_stage != candidate.get("stage"):
            if candidate.get("stage") == "Joined" or candidate.get("outcome") in ("Rejected", "Withdrawn"):
                return Response(
                    {"detail": "This candidate's recruitment is closed; the stage can no longer be changed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if new_stage == "Joined":
                return Response(
                    {"detail": "A candidate moves to Onboarding automatically once recruitment is complete and the outcome is Selected."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if new_stage in ("Rejected", "Withdrawn"):
                data["outcome"] = new_stage
            write_audit(
                "candidate", cand_id, "stage_changed",
                candidate.get("stage"), new_stage, request,
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

        get_reference_checks_collection().delete_many({"candidate_id": cand_id})
        get_candidates_collection().delete_one({"id": cand_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


def _step_response(request, cand_id, step_id, new_status, notes=None):
    updated, transition = apply_candidate_step_status(
        request, cand_id, step_id, new_status, notes
    )
    return Response(serialize_candidate(updated, transition=transition))


class CandidateStepDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, step_id):
        return _step_response(request, cand_id, step_id, "Completed")


class CandidateStepUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, step_id):
        return _step_response(request, cand_id, step_id, "Pending")


class CandidateStepStatusView(APIView):
    """POST {status: Pending | In Progress | Completed, notes?}"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, step_id):
        serializer = StepStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return _step_response(request, cand_id, step_id, data["status"], data.get("notes"))


class CandidateOutcomeView(APIView):
    """POST {outcome: Selected | Rejected | Withdrawn}"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CandidateOutcomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = serializer.validated_data["outcome"]
        previous = candidate.get("outcome")

        if candidate.get("onboarding_employee_id"):
            return Response(
                {"detail": "This candidate has already moved to Onboarding; the outcome can no longer change."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if previous in ("Rejected", "Withdrawn") and previous != outcome:
            return Response(
                {"detail": "A Rejected / Withdrawn candidate cannot be reopened."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update = {"outcome": outcome}
        if outcome in ("Rejected", "Withdrawn"):
            update["stage"] = outcome
        get_candidates_collection().update_one({"id": cand_id}, {"$set": update})

        if previous != outcome:
            write_audit("candidate", cand_id, "outcome_changed", previous, outcome, request)
        if update.get("stage") and update["stage"] != candidate.get("stage"):
            write_audit(
                "candidate", cand_id, "stage_changed",
                candidate.get("stage"), update["stage"], request,
            )

        transition = None
        if outcome == "Selected":
            transition = evaluate_candidate_transition(cand_id, request)

        return Response(serialize_candidate(get_candidate_by_id(cand_id), transition=transition))


class CandidateUnfreezeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"frozen": False, "frozen_reason": ""}}
        )
        write_audit("candidate", cand_id, "unfrozen", True, False, request)
        transition = evaluate_candidate_transition(cand_id, request)
        updated = get_candidate_by_id(cand_id)
        return Response(serialize_candidate(updated, transition=transition))


class CandidateCreateEmployeeView(APIView):
    """HR clicks "Move to Onboarding". Kept at the original URL (create-employee/).

    Allowed only when the backend confirms ALL of: required recruitment steps
    completed, outcome Selected, not frozen, stage Documents Pending, and every
    required document uploaded. Atomic and idempotent (see lifecycle.transitions).
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response(
                {"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND
            )

        ready, reason = candidate_transition_status(candidate)
        if not ready:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        result = move_candidate_to_onboarding(candidate, request)
        if not result.get("moved"):
            return Response(
                {"detail": result.get("reason", "Could not move the candidate to onboarding.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "employee_id": result["employee_id"],
                "position_id": result["position_id"],
                "message": result["message"],
            },
            status=status.HTTP_201_CREATED,
        )
