"""Position assignment and release shared by recruitment and separation."""
from datetime import date

from django.utils import timezone

from database.collections import get_employees_collection, get_positions_collection
from database.queries import generate_next_sequential_id, get_employee_by_pk


def get_position_by_id(pos_id):
    return get_positions_collection().find_one({"id": pos_id})


def find_or_create_vacant_position(designation, department, branch):
    """Reused by the candidate->employee and onboarding flows: find an existing
    vacant position matching designation/department/branch, or auto-create one."""
    position = get_positions_collection().find_one(
        {
            "status": "Vacant",
            "designation": designation,
            "department": department,
            "branch": branch,
        }
    )
    if position:
        return position

    position_doc = {
        "id": generate_next_sequential_id(get_positions_collection(), "POS"),
        "designation": designation,
        "department": department,
        "branch": branch,
        "status": "Vacant",
        "current_employee_id": None,
        "created_at": timezone.now().isoformat(),
        "history": [],
    }
    get_positions_collection().insert_one(position_doc)
    return position_doc


def assign_employee_to_position(position, employee):
    """Core assign logic, reused by PositionAssignView and by the candidate->
    employee conversion flow. Caller is responsible for checking the position
    is vacant and the employee doesn't already hold one."""
    today = date.today().isoformat()
    employee_id = str(employee["_id"])
    history_entry = {
        "employee_id": employee_id,
        "employee_name": employee.get("name", ""),
        "start_date": today,
        "end_date": None,
    }

    get_positions_collection().update_one(
        {"_id": position["_id"]},
        {
            "$set": {"current_employee_id": employee_id, "status": "Active"},
            "$push": {"history": history_entry},
        },
    )
    get_employees_collection().update_one(
        {"_id": employee["_id"]}, {"$set": {"position_id": position["id"]}}
    )


def unassign_position(position):
    """Core unassign logic, reused by PositionUnassignView and by the exit/
    separation flow, which vacates a position automatically once the exit
    checklist is fully complete."""
    today = date.today().isoformat()
    current_employee_id = position.get("current_employee_id")

    get_positions_collection().update_one(
        {"_id": position["_id"]},
        {
            "$set": {
                "current_employee_id": None,
                "status": "Vacant",
                "history.$[open].end_date": today,
            }
        },
        array_filters=[{"open.end_date": None}],
    )

    if current_employee_id:
        employee = get_employee_by_pk(current_employee_id)
        if employee:
            get_employees_collection().update_one(
                {"_id": employee["_id"]}, {"$unset": {"position_id": ""}}
            )


def unassign_position_for_employee(employee_id):
    """Looks up whichever position an employee currently holds (if any) and
    vacates it. Used by the exit/separation flow where we know the employee
    id but not necessarily their position id."""
    position = get_positions_collection().find_one({"current_employee_id": employee_id})
    if position:
        unassign_position(position)
