"""Workflow operations; API views own parsing and responses."""
from rest_framework.exceptions import NotFound, ValidationError

from database.collections import get_employees_collection
from database.queries import get_employee_by_pk
from lifecycle.audit import user_label, write_audit
from lifecycle.steps import normalize_steps, set_step_status


def apply_onboarding_step_status(request, pk, step_id, new_status, notes=None):
    from lifecycle.transitions import evaluate_onboarding_completion

    employee = get_employee_by_pk(pk)
    if not employee:
        raise NotFound({'detail': 'Employee not found.'})

    if employee.get("status") != "Onboarding":
        raise ValidationError({'detail': 'Onboarding is already complete for this employee; its history is read-only.'})

    steps = normalize_steps(employee.get("onboarding_steps", []))
    step = next((s for s in steps if s.get("id") == step_id), None)
    if not step:
        raise NotFound({'detail': 'Onboarding step not found.'})

    previous = set_step_status(step, new_status, user_label(request), notes)
    get_employees_collection().update_one(
        {"_id": employee["_id"]}, {"$set": {"onboarding_steps": steps}}
    )
    if previous != new_status:
        write_audit(
            "employee", str(employee["_id"]), "onboarding_step_status_changed",
            previous, new_status, request,
            {"step_no": step.get("step_no"), "step": step.get("how") or step.get("step_name", "")},
        )

    transition = evaluate_onboarding_completion(str(employee["_id"]), request)
    updated = get_employees_collection().find_one({"_id": employee["_id"]})
    return updated, transition
