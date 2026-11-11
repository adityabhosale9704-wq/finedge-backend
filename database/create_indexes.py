"""Idempotent MongoDB index creation for FinEdge HR OS (perf/speed-up, Phase 1).

Safe to run multiple times: pymongo's create_index() is a no-op if an
identical index already exists, and only adds a new one if it doesn't.
Does NOT change any collection's data, any API response shape, or any
field name — only adds index structures Mongo uses internally to avoid
full collection scans.

Usage:
    (venv) python -m database.create_indexes

Run this against the SAME database the app actually uses (reads
MONGO_URI / MONGO_DB_NAME from the root .env via database.connection).
"""

import argparse
from pymongo import ASCENDING

from database.connection import get_database


# Each entry: (collection, [(field, unique?), ...])
# "Already exists" ones are listed too — safe (no-op) — so this script is
# a single source of truth for every index the app needs, not just the gaps.
INDEX_PLAN = [
    ("users", [("email", False)]),
    ("employees", [("branch", False), ("status", False)]),
    ("branches", [("code", True)]),
    ("roles", [("department_id", False)]),
    ("candidates", [("id", False), ("requisition_id", False)]),
    ("requisitions", [("id", False)]),
    ("tasks", [("id", False)]),
    ("positions", [("id", False), ("current_employee_id", False)]),
    ("separations", [("id", False), ("employee_id", False)]),
    ("workindia_candidates", [("id", False), ("stage", False), ("excluded", False)]),
    ("salary_revisions", [("id", False)]),
    ("reference_checks", [("candidate_id", False)]),
    ("workflow_templates", [("type", False)]),
    # SOP Configuration (Phase 1). Compound entries are written as a tuple of
    # field names. (process_type, step_no) unique = step numbers can never
    # collide, even if two admins add a step at the same moment.
    ("sop_templates", [("id", True), (("process_type", "step_no"), True)]),
    # Audit trail: fast "history of this record" lookups.
    ("audit_log", [(("entity_type", "entity_id", "at"), False)]),
    # One employee per candidate (Phase 3/4). Partial: older employees have no
    # source_candidate_id, and those must not collide with each other.
    ("employees", [(("source_candidate_id",), True, {"source_candidate_id": {"$type": "string"}})]),
    # One OPEN exit per employee (Phase 5). Partial on status == "In Progress",
    # so completed exits (history) never block a later one.
    ("separations", [(("employee_id",), True, {"status": "In Progress"})]),
]


def find_duplicates(collection, field_names, partial_filter):
    """Existing duplicate keys that would make a UNIQUE index fail to build."""
    match = dict(partial_filter or {})
    pipeline = []
    if match:
        pipeline.append({"$match": match})
    pipeline += [
        {"$group": {"_id": {n: "$" + n for n in field_names}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
        {"$limit": 5},
    ]
    return list(collection.aggregate(pipeline))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be created (and any blocking duplicates) without creating anything",
    )
    args = parser.parse_args()

    create_indexes(get_database(), dry_run=args.dry_run)


def create_indexes(db, dry_run=False):
    for collection_name, fields in INDEX_PLAN:
        collection = db[collection_name]
        for entry in fields:
            field, unique = entry[0], entry[1]
            partial_filter = entry[2] if len(entry) > 2 else None
            field_names = field if isinstance(field, tuple) else (field,)
            label = f"{collection_name}.{'+'.join(field_names)}" + (" (unique)" if unique else "")

            if unique:
                duplicates = find_duplicates(collection, field_names, partial_filter)
                if duplicates:
                    print(f"SKIPPED {label}: existing duplicate keys would block it (values withheld).")
                    print("        Clean those up, then re-run this script.")
                    continue

            if dry_run:
                print(f"would create {label}")
                continue

            kwargs = {"unique": unique}
            if partial_filter:
                kwargs["partialFilterExpression"] = partial_filter
                # Partial and ordinary indexes can share fields, but not a name.
                kwargs["name"] = "_".join(field_names) + "_partial_unique"
            index_name = collection.create_index(
                [(name, ASCENDING) for name in field_names], **kwargs
            )
            print(f"{label} -> {index_name}")

    print()
    print("Done. Re-run any time. Existing indexes are left untouched.")


if __name__ == "__main__":
    main()
