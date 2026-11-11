"""First-use seeding of sop_templates.

Runs only when the collection is completely empty. For each process type it
prefers the steps already configured in the legacy `workflow_templates`
collection (so nothing the admin set up is lost); if that has none, it falls
back to the built-in defaults below.

Mapping from a legacy step {step_name, who, tat_days}:
    how      <- step_name
    when     <- "Within N day(s)" (from tat_days)
    who      <- who (or "HR" if it was blank, because `who` is mandatory now)
    required <- True

Safe to call repeatedly and concurrently: it is a no-op once any document
exists, and the unique (process_type, step_no) index makes a racing second
insert fail harmlessly.
"""

import uuid

from django.utils import timezone
from pymongo.errors import BulkWriteError

from database.collections import get_sop_templates_collection
from sop.serializers import PROCESS_TYPES
from database.collections import get_workflow_templates_collection

# (who, when, how, tat_days)
DEFAULT_SOP_STEPS = {
    "recruitment": [
        ("Recruiter", "Within 2 days of application", "Screen the resume against the requisition and shortlist.", 2),
        ("Hiring Manager", "Within 3 days of shortlisting", "Conduct the technical / functional interview and record feedback.", 3),
        ("HR Manager", "Within 2 days of the technical round", "Conduct the HR interview and discuss expectations and CTC.", 2),
        ("HR Head", "Within 1 day of the HR interview", "Approve the offer, CTC and joining date.", 1),
    ],
    "onboarding": [
        ("HR Manager", "Before the joining date", "Collect and verify joining documents.", 1),
        ("IT Team", "Before the joining date", "Create email / system access and issue the laptop.", 1),
        ("Employee", "On the joining date", "Read and accept the policy handbook.", 1),
        ("HR Manager", "Within the first week", "Conduct the induction and introduce the team.", 1),
    ],
    "exit": [
        ("Manager", "On receipt of resignation", "Accept the resignation and confirm the last working day.", 1),
        ("Employee", "During the notice period", "Complete the knowledge transfer and handover.", 7),
        ("Admin / IT", "Before the last working day", "Collect company assets and revoke system access.", 2),
        ("Finance", "After the last working day", "Prepare and release the full and final settlement.", 5),
    ],
}


def _legacy_steps(process_type):
    template = get_workflow_templates_collection().find_one(
        {"type": PROCESS_TYPES[process_type]}
    )
    if not template:
        return []
    steps = sorted(template.get("steps", []), key=lambda s: s.get("sort_order", 0))
    return [
        (
            (s.get("who") or "").strip() or "HR",
            f"Within {s.get('tat_days', 1)} day(s)",
            (s.get("step_name") or "").strip() or "Complete this step.",
            s.get("tat_days", 1),
        )
        for s in steps
    ]


def build_seed_documents():
    now = timezone.now().isoformat()
    documents = []
    report = {}
    for process_type in PROCESS_TYPES:
        rows = _legacy_steps(process_type)
        source = "workflow_templates"
        if not rows:
            rows = DEFAULT_SOP_STEPS[process_type]
            source = "defaults"
        report[process_type] = {"source": source, "steps": len(rows)}
        for index, (who, when, how, tat_days) in enumerate(rows, start=1):
            documents.append(
                {
                    "id": uuid.uuid4().hex,
                    "process_type": process_type,
                    "step_no": index,
                    "who": who,
                    "when": when,
                    "how": how,
                    "required": True,
                    "active": True,
                    "tat_days": tat_days,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return documents, report


def seed_if_empty(dry_run=False):
    collection = get_sop_templates_collection()
    if collection.count_documents({}, limit=1) > 0:
        return {"seeded": False, "reason": "sop_templates is not empty"}

    documents, report = build_seed_documents()
    if dry_run:
        return {"seeded": False, "dry_run": True, "would_insert": len(documents), "plan": report}

    try:
        collection.insert_many(documents, ordered=False)
    except BulkWriteError:
        # Another request seeded at the same moment; the unique index rejected ours.
        return {"seeded": False, "reason": "seeded concurrently"}
    return {"seeded": True, "inserted": len(documents), "plan": report}
