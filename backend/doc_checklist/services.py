"""Joining checklist defaults and idempotent initialization."""
import uuid

from database.collections import get_candidates_collection

DOCUMENT_CATEGORIES = [
    ("Identification", ["Aadhaar Card", "PAN Card", "Passport-size Photo"]),
    ("Address Proof", ["Utility Bill / Rent Agreement"]),
    ("Education", ["Highest Qualification Certificate", "Marksheet"]),
    (
        "Employment & Experience",
        ["Previous Offer Letter", "Relieving Letter", "Experience Certificate"],
    ),
    ("Financial & Tax", ["Bank Passbook / Cancelled Cheque", "Form 16 / Previous Salary Slip"]),
]


def build_default_checklist():
    items = []
    for category, doc_names in DOCUMENT_CATEGORIES:
        for doc_name in doc_names:
            items.append(
                {
                    "id": uuid.uuid4().hex,
                    "category": category,
                    "doc_name": doc_name,
                    "status": "Pending",
                    "file_url": "",
                    "rejection_reason": "",
                }
            )
    return items


def snapshot_doc_checklist_for_candidate(cand_id):
    """Called once a candidate's stage becomes Documents Pending. Idempotent —
    does nothing if the candidate already has a checklist (so re-entering the
    stage, or calling this more than once, never wipes HR's verification work)."""
    candidate = get_candidates_collection().find_one({"id": cand_id})
    if not candidate or candidate.get("doc_checklist"):
        return

    get_candidates_collection().update_one(
        {"id": cand_id},
        {
            "$set": {
                "doc_checklist": build_default_checklist(),
                "additional_docs": {
                    "uan_number": "",
                    "marital_status": "",
                    "nominee_docs": [],
                },
                "upload_token": None,
            }
        },
    )
