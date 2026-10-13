"""Shared step logic for recruitment, onboarding and exit.

A step copied from the SOP looks like:
    {id, step_no, who, when, how, required, tat_days,
     status, completed_at, completed_by, notes, done, done_date}

`status` is the source of truth (Pending / In Progress / Completed).
`done` / `done_date` are kept in sync so every older screen (Done Board,
notifications, ...) that still reads them keeps working. Steps copied before
this feature existed have only `done`; normalize_step() reads those correctly.
"""

from datetime import date

from django.utils import timezone

STEP_STATUSES = ["Pending", "In Progress", "Completed"]


def normalize_step(step):
    step = dict(step)
    if step.get("status") not in STEP_STATUSES:
        step["status"] = "Completed" if step.get("done") else "Pending"
    step["done"] = step["status"] == "Completed"
    step.setdefault("required", True)
    step.setdefault("notes", "")
    step.setdefault("completed_at", None)
    step.setdefault("completed_by", None)
    step.setdefault("when", "")
    step.setdefault("how", step.get("step_name", ""))
    return step


def normalize_steps(steps):
    normalized = [normalize_step(s) for s in (steps or [])]
    for index, step in enumerate(normalized, start=1):
        step.setdefault("step_no", index)
    return normalized


def set_step_status(step, new_status, performed_by, notes=None):
    """Mutates `step` in place; returns the previous status."""
    previous = normalize_step(step)["status"]
    step["status"] = new_status
    step["done"] = new_status == "Completed"
    if new_status == "Completed":
        step["done_date"] = date.today().isoformat()
        step["completed_at"] = timezone.now().isoformat()
        step["completed_by"] = performed_by
    else:
        step["done_date"] = None
        step["completed_at"] = None
        step["completed_by"] = None
    if notes is not None:
        step["notes"] = notes
    return previous


def compute_progress(steps):
    """Progress is calculated on the backend; the UI only displays it."""
    steps = normalize_steps(steps)
    total = len(steps)
    completed = len([s for s in steps if s["status"] == "Completed"])
    required = [s for s in steps if s["required"]]
    required_completed = len([s for s in required if s["status"] == "Completed"])
    current = next((s for s in steps if s["status"] != "Completed"), None)
    return {
        "progress_pct": round(completed * 100 / total) if total else 0,
        "steps_total_count": total,
        "steps_done_count": completed,
        "required_total_count": len(required),
        "required_done_count": required_completed,
        "all_required_completed": total > 0 and required_completed == len(required),
        "current_step": (
            {"id": current["id"], "step_no": current.get("step_no"), "how": current.get("how", ""), "who": current.get("who", "")}
            if current
            else None
        ),
        "pending_tasks": [
            f"{s.get('step_no')}. {s.get('how') or s.get('step_name', '')}".strip()
            for s in steps
            if s["status"] != "Completed"
        ],
    }
