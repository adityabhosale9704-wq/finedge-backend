"""Workflow operations; API views own parsing and responses."""
from rest_framework.exceptions import NotFound, ValidationError

from database.collections import get_candidates_collection
from database.queries import get_candidate_by_id
from doc_checklist.services import snapshot_doc_checklist_for_candidate
from lifecycle.audit import user_label, write_audit
from lifecycle.steps import compute_progress, normalize_steps, set_step_status
from lifecycle.transitions import evaluate_candidate_transition


def apply_candidate_step_status(request, cand_id, step_id, new_status, notes=None):
    """Single place every candidate step change goes through, so validation,
    progress, audit and onboarding eligibility cannot diverge."""
    candidate = get_candidate_by_id(cand_id)
    if not candidate:
        raise NotFound({'detail': 'Candidate not found.'})

    if candidate.get("frozen"):
        raise ValidationError({'detail': "This candidate's file is frozen pending a reference check discrepancy review. Resolve it and unfreeze before continuing."})

    if candidate.get("outcome") in ("Rejected", "Withdrawn") or candidate.get("stage") in (
        "Rejected",
        "Withdrawn",
    ):
        raise ValidationError({'detail': "This candidate's recruitment is closed (Rejected / Withdrawn)."})

    if candidate.get("onboarding_employee_id"):
        raise ValidationError({'detail': 'This candidate has already moved to Onboarding. Recruitment history is read-only.'})

    steps = normalize_steps(candidate.get("steps", []))
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        raise NotFound({'detail': 'Step not found.'})

    previous = set_step_status(step, new_status, user_label(request), notes)

    update = {"steps": steps}
    progress = compute_progress(steps)
    if progress["all_required_completed"] and candidate.get("stage") != "Documents Pending":
        update["stage"] = "Documents Pending"

    get_candidates_collection().update_one({"id": cand_id}, {"$set": update})

    if previous != new_status:
        write_audit(
            "candidate", cand_id, "step_status_changed", previous, new_status, request,
            {"step_no": step.get("step_no"), "step": step.get("how") or step.get("step_name", "")},
        )
    if update.get("stage"):
        write_audit(
            "candidate", cand_id, "stage_changed",
            candidate.get("stage"), update["stage"], request,
        )
        snapshot_doc_checklist_for_candidate(cand_id)

    transition = evaluate_candidate_transition(cand_id, request)
    return get_candidate_by_id(cand_id), transition
