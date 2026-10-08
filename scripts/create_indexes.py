"""Idempotent MongoDB index creation for FinEdge HR OS (perf/speed-up, Phase 1).

Safe to run multiple times: pymongo's create_index() is a no-op if an
identical index already exists, and only adds a new one if it doesn't.
Does NOT change any collection's data, any API response shape, or any
field name — only adds index structures Mongo uses internally to avoid
full collection scans.

Usage:
    (venv) python scripts/create_indexes.py

Run this against the SAME database the app actually uses (reads
MONGO_URI / MONGO_DB_NAME from .env, exactly like every app's mongo.py).
"""

import os

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "finedge")


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
]


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    for collection_name, fields in INDEX_PLAN:
        collection = db[collection_name]
        for field, unique in fields:
            index_name = collection.create_index(
                [(field, ASCENDING)], unique=unique
            )
            print(f"{collection_name}.{field} -> {index_name}" + (" (unique)" if unique else ""))

    print("\nDone. Re-run any time — existing indexes are left untouched.")


if __name__ == "__main__":
    main()
