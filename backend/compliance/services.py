"""Shared status calculation; no request or response objects."""
from datetime import date


def compute_status(next_due_date):
    days_left = (next_due_date - date.today()).days
    if days_left < 0:
        return "red"
    if days_left <= 30:
        return "amber"
    return "green"
