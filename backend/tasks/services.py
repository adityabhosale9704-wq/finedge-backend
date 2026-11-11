"""Shared status calculation; no request or response objects."""
from datetime import date


def compute_task_status(doc):
    due_date = date.fromisoformat(doc["due_date"])

    if doc.get("done"):
        done_date = date.fromisoformat(doc["done_date"])
        if done_date < due_date:
            return "Early"
        if done_date == due_date:
            return "On Time"
        return "Delayed"

    if date.today() > due_date:
        return "Overdue"
    return "Open"
