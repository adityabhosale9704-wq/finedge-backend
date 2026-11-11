"""Lifecycle transitions, validated entirely on the backend.

    Recruitment -> Documents Pending   automatic: all required recruitment steps done
    Documents Pending -> Onboarding    HR clicks "Move to Onboarding" once the outcome is
                                       Selected and every required document is uploaded
    Onboarding -> Active employee      automatic: all required onboarding steps done
                                       + policy accepted

Onboarding creation and activation are idempotent: they are guarded by a CONDITIONAL update (the filter only
matches while the record is still in the "from" state), so a repeated trigger,
a double-click or two simultaneous requests can only win once. The unique index
on employees.source_candidate_id is a second line of defence against duplicates.

"""

from datetime import date

from positions.services import assign_employee_to_position, find_or_create_vacant_position

from django.utils import timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database.collections import get_employees_collection
from lifecycle.audit import user_label, write_audit
from lifecycle.docs import required_docs_summary
from lifecycle.steps import compute_progress
from database.collections import get_candidates_collection, get_requisitions_collection
from workflows.services import snapshot_steps_for_instance

MOVED_TO_ONBOARDING_MESSAGE = "Candidate successfully moved to Onboarding."
ONBOARDING_DONE_MESSAGE = "Onboarding completed. Employee added to the Employee List."


def _docs_ok(candidate, force_docs=False):
    return required_docs_summary(candidate)["all_uploaded"]


def candidate_transition_status(candidate, force_docs=False):
    """Returns (ready, reason). `reason` explains what is still missing."""
    if candidate.get("outcome") in ("Rejected", "Withdrawn"):
        return False, "Candidate was " + candidate["outcome"].lower() + "."
    if candidate.get("onboarding_employee_id"):
        return False, "Already moved to onboarding."
    if candidate.get("frozen"):
        return False, "Candidate file is frozen pending a reference check review."
    if not compute_progress(candidate.get("steps"))["all_required_completed"]:
        return False, "Required recruitment steps are not all completed."
    if candidate.get("outcome") != "Selected":
        return False, "Outcome must be set to Selected."
    if candidate.get("stage") != "Documents Pending":
        return False, "Candidate is not at the Documents Pending stage."
    if not _docs_ok(candidate, force_docs):
        summary = required_docs_summary(candidate)
        return False, (
            f"Upload all required documents first ({summary['required_uploaded_count']}"
            f"/{summary['required_total_count']} uploaded)."
        )
    return True, ""


def evaluate_candidate_transition(cand_id, request, force_docs=False):
    """Report whether the candidate can now be moved to onboarding.

    This does NOT move anyone: the move is an explicit HR action
    (move_candidate_to_onboarding, via the "Move to Onboarding" button).
    Returns {"moved": False, "ready": bool, "reason": str}.
    """
    candidate = get_candidates_collection().find_one({"id": cand_id})
    if not candidate:
        return {"moved": False, "ready": False, "reason": "Candidate not found."}

    ready, reason = candidate_transition_status(candidate, force_docs)
    return {"moved": False, "ready": ready, "reason": reason}


def move_candidate_to_onboarding(candidate, request, force_docs=False):
    cand_id = candidate["id"]
    now = timezone.now().isoformat()

    # Atomic claim: only ONE caller can flip the candidate out of
    # "Documents Pending" while it has no onboarding employee yet.
    claimed = get_candidates_collection().find_one_and_update(
        {
            "id": cand_id,
            "stage": "Documents Pending",
            "outcome": "Selected",
            "frozen": {"$ne": True},
            "onboarding_employee_id": None,
        },
        {"$set": {"stage": "Joined", "onboarding_started_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        return {"moved": False, "reason": "Already moved or no longer eligible."}

    requisition = None
    if claimed.get("requisition_id"):
        requisition = get_requisitions_collection().find_one({"id": claimed["requisition_id"]})
    designation = requisition.get("role", "") if requisition else ""
    branch = requisition.get("branch", "") if requisition else ""
    department = ""

    employee_doc = {
        "name": claimed.get("name", ""),
        "email": claimed.get("email", ""),
        "phone": claimed.get("phone", ""),
        "department": department,
        "designation": designation,
        "branch": branch,
        "date_of_joining": date.today().isoformat(),
        "ctc": 0,
        "status": "Onboarding",
        "lifecycle_stage": "Onboarding",
        "family": [],
        "onboarding_steps": snapshot_steps_for_instance("Onboarding"),
        "onboarding_started_at": now,
        "source_candidate_id": cand_id,
    }

    try:
        result = get_employees_collection().insert_one(employee_doc)
        employee_doc["_id"] = result.inserted_id
    except DuplicateKeyError:
        existing = get_employees_collection().find_one({"source_candidate_id": cand_id})
        if existing:
            get_candidates_collection().update_one(
                {"id": cand_id}, {"$set": {"onboarding_employee_id": str(existing["_id"])}}
            )
            return {"moved": False, "reason": "Already moved to onboarding."}
        raise
    except Exception:
        # Roll back the candidate claim when employee insertion fails.
        get_candidates_collection().update_one(
            {"id": cand_id},
            {"$set": {"stage": "Documents Pending"}, "$unset": {"onboarding_started_at": ""}},
        )
        raise

    employee_id = str(employee_doc["_id"])
    get_candidates_collection().update_one(
        {"id": cand_id},
        {"$set": {"onboarding_employee_id": employee_id, "lifecycle_status": "Onboarding"}},
    )

    position = find_or_create_vacant_position(designation, department, branch)
    assign_employee_to_position(position, employee_doc)

    write_audit(
        "candidate", cand_id, "stage_transition",
        "Recruitment", "Onboarding", request,
        {"employee_id": employee_id, "position_id": position["id"], "docs_override": bool(force_docs)},
    )
    write_audit(
        "employee", employee_id, "created_from_candidate",
        None, "Onboarding", request, {"candidate_id": cand_id},
    )

    return {
        "moved": True,
        "message": MOVED_TO_ONBOARDING_MESSAGE,
        "employee_id": employee_id,
        "position_id": position["id"],
    }


def onboarding_completion_status(employee):
    if employee.get("status") != "Onboarding":
        return False, "Employee is not in onboarding."
    if not compute_progress(employee.get("onboarding_steps"))["all_required_completed"]:
        return False, "Required onboarding steps are not all completed."
    if not employee.get("policy_accepted"):
        return False, "The policy handbook must be accepted first."
    return True, ""


def evaluate_onboarding_completion(employee_id, request):
    """Activate the employee when every required onboarding step is done."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        object_id = ObjectId(employee_id)
    except (InvalidId, TypeError):
        return {"moved": False, "reason": "Employee not found."}

    employee = get_employees_collection().find_one({"_id": object_id})
    if not employee:
        return {"moved": False, "reason": "Employee not found."}

    ready, reason = onboarding_completion_status(employee)
    if not ready:
        return {"moved": False, "reason": reason}

    # Conditional update: succeeds for exactly one caller.
    result = get_employees_collection().update_one(
        {"_id": object_id, "status": "Onboarding"},
        {
            "$set": {
                "status": "Active",
                "lifecycle_stage": "Active",
                "onboarding_completed_at": timezone.now().isoformat(),
            }
        },
    )
    if result.modified_count != 1:
        return {"moved": False, "reason": "Already activated."}

    candidate_id = employee.get("source_candidate_id")
    if candidate_id:
        get_candidates_collection().update_one(
            {"id": candidate_id}, {"$set": {"lifecycle_status": "Employee"}}
        )
        write_audit(
            "candidate", candidate_id, "lifecycle_status_changed",
            "Onboarding", "Employee", request, {"employee_id": employee_id},
        )

    write_audit(
        "employee", employee_id, "stage_transition",
        "Onboarding", "Active", request, {"by": user_label(request)},
    )
    return {"moved": True, "message": ONBOARDING_DONE_MESSAGE, "employee_id": employee_id}


