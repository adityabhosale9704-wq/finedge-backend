"""Workflow operations; API views own parsing and responses."""
from django.utils import timezone
from pymongo.errors import DuplicateKeyError
from rest_framework.exceptions import NotFound, ValidationError

from accounts.rbac import require_hr_admin
from database.collections import get_employees_collection, get_separations_collection
from database.queries import generate_next_sequential_id, get_employee_by_pk
from lifecycle.audit import user_label, write_audit
from lifecycle.steps import compute_progress, normalize_steps, set_step_status
from positions.services import unassign_position_for_employee
from workflows.services import snapshot_steps_for_instance

EXIT_COMPLETED_MESSAGE = "Exit & Separation process completed."


def get_separation_by_id(sep_id):
    return get_separations_collection().find_one({"id": sep_id})


def separation_is_complete(doc):
    if doc.get("status"):
        return doc["status"] == "Completed"
    # Older records have no `status`: derive it from their steps.
    steps = doc.get("steps", [])
    return len(steps) > 0 and all(s.get("done") for s in steps)


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
        raise ValidationError({'detail': 'An exit can only be initiated for a current employee (this one is ' + str(employee.get('status', '')) + ').'})

    if open_separation_for(employee_id):
        raise ValidationError({'detail': 'This employee already has an exit process in progress.'})

    if notice_period_days is None:
        notice_period_days = max((last_working_day - resignation_date).days, 0)

    separation_doc = {
        "id": generate_next_sequential_id(get_separations_collection(), "SEP"),
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
        raise ValidationError({'detail': 'This employee already has an exit process in progress.'})

    write_audit(
        "separation", separation_doc["id"], "exit_initiated", None, "In Progress", request,
        {"employee_id": employee_id, "last_working_day": separation_doc["last_working_day"]},
    )
    write_audit(
        "employee", employee_id, "exit_initiated", None, separation_doc["id"], request,
        {"resignation_date": separation_doc["resignation_date"], "reason": reason},
    )
    return separation_doc


def apply_separation_step_status(request, sep_id, step_id, new_status, notes=None):
    separation = get_separation_by_id(sep_id)
    if not separation:
        raise NotFound({'detail': 'Separation not found.'})

    if separation.get("status") == "Completed":
        raise ValidationError({'detail': 'This exit process is completed; its history is read-only.'})

    steps = normalize_steps(separation.get("steps", []))
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        raise NotFound({'detail': 'Step not found.'})

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

    return get_separation_by_id(sep_id), transition
