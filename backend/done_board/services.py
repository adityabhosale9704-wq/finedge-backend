"""Pending workflow aggregation shared by Done Board and notifications."""

from database.collections import (
    get_candidates_collection,
    get_employees_collection,
    get_separations_collection,
)
from database.queries import build_employee_name_lookup

CANDIDATE_TERMINAL_STAGES = {"Joined", "Rejected", "Withdrawn"}


def first_undone_step(steps):
    for step in steps or []:
        if not step.get("done"):
            return step
    return None


def list_pending_steps():
    items = []

    for candidate in get_candidates_collection().find():
        if candidate.get("stage") in CANDIDATE_TERMINAL_STAGES:
            continue
        step = first_undone_step(candidate.get("steps"))
        if step:
            items.append({
                "module": "recruitment",
                "person_name": candidate.get("name"),
                "record_id": candidate.get("id"),
                "step_id": step.get("id"),
                "step_name": step.get("step_name"),
                "who": step.get("who"),
            })

    for employee in get_employees_collection().find({"status": "Onboarding"}):
        step = first_undone_step(employee.get("onboarding_steps"))
        if step:
            items.append({
                "module": "onboarding",
                "person_name": employee.get("name"),
                "record_id": str(employee["_id"]),
                "step_id": step.get("id"),
                "step_name": step.get("step_name"),
                "who": step.get("who"),
            })

    in_progress_separations = []
    for separation in get_separations_collection().find():
        steps = separation.get("steps", [])
        done_count = sum(1 for s in steps if s.get("done"))
        is_complete = len(steps) > 0 and done_count == len(steps)
        if is_complete:
            continue
        step = first_undone_step(steps)
        if step:
            in_progress_separations.append((separation, step))

    employee_name_lookup = build_employee_name_lookup(
        s.get("employee_id") for s, _ in in_progress_separations if s.get("employee_id")
    )
    for separation, step in in_progress_separations:
        employee_id = separation.get("employee_id")
        items.append({
            "module": "exit",
            "person_name": employee_name_lookup.get(employee_id, employee_id),
            "record_id": separation.get("id"),
            "step_id": step.get("id"),
            "step_name": step.get("step_name"),
            "who": step.get("who"),
        })

    return items
