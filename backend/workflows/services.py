"""Independent workflow snapshots for new HR records."""
import uuid


def snapshot_steps_for_instance(workflow_type):
    """Build a fresh, independent copy of a workflow template's steps to attach
    to a specific candidate/employee/separation record. Each snapshot gets its
    own step ids (separate from the template's) plus done/done_date fields, so
    later edits to the admin template never retroactively change records that
    already copied it — matching this app's existing snapshot pattern (see
    employees' family/facilities arrays, recruitment's candidate creation)."""
    # The source of truth is now the SOP Configuration (sop_templates), which
    # is seeded from the legacy workflow_templates on first use. Only ACTIVE
    # steps are copied. `done` / `done_date` are kept alongside the new
    # `status` so every existing screen keeps working unchanged.
    from sop.service import list_steps

    return [
        {
            "id": uuid.uuid4().hex,
            "step_no": step["step_no"],
            "step_name": step.get("how", ""),
            "who": step.get("who", ""),
            "when": step.get("when", ""),
            "how": step.get("how", ""),
            "required": step.get("required", True),
            "tat_days": step.get("tat_days", 1),
            "status": "Pending",
            "done": False,
            "done_date": None,
            "completed_at": None,
            "completed_by": None,
            "notes": "",
        }
        for step in list_steps(workflow_type.lower(), only_active=True)
    ]
