"""Shared lookups used by several HR features."""
from bson import ObjectId
from bson.errors import InvalidId

from database.collections import (
    get_candidates_collection,
    get_employees_collection,
    get_requisitions_collection,
)


def get_employee_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_employees_collection().find_one({"_id": object_id})


def generate_next_sequential_id(collection, prefix):
    # shortcut: max-plus-one IDs can race; use an atomic counter for concurrent creation.
    max_num = 0
    for doc in collection.find({}, {"id": 1}):
        value = doc.get("id", "")
        if value.startswith(prefix + "-"):
            try:
                max_num = max(max_num, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{max_num + 1:04d}"


def get_requisition_by_id(req_id):
    return get_requisitions_collection().find_one({"id": req_id})


def get_candidate_by_id(cand_id):
    return get_candidates_collection().find_one({"id": cand_id})


def build_employee_name_lookup(employee_ids):
    """One batched query instead of one lookup per row — avoids N+1 queries
    when serializing a list of positions/separations/etc."""
    object_ids = []
    for employee_id in employee_ids:
        try:
            object_ids.append(ObjectId(employee_id))
        except (InvalidId, TypeError):
            continue
    if not object_ids:
        return {}
    employees = get_employees_collection().find(
        {"_id": {"$in": object_ids}}, {"name": 1}
    )
    return {str(e["_id"]): e.get("name", "") for e in employees}
