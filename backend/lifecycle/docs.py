"""Which joining documents are required, and are they uploaded yet?

A checklist item counts as UPLOADED when it has a file and has not been
rejected (a rejected document must be uploaded again). Verification is a
separate, optional review step: it does not gate moving to onboarding.
Items default to required; set `required: False` on an item to make it optional.
"""


def required_docs_summary(candidate):
    items = [d for d in candidate.get("doc_checklist", []) if d.get("required", True)]
    uploaded = [d for d in items if d.get("file_url") and d.get("status") != "Rejected"]
    return {
        "required_total_count": len(items),
        "required_uploaded_count": len(uploaded),
        "all_uploaded": len(uploaded) == len(items),
        "missing": [d.get("doc_name", "") for d in items if d not in uploaded],
    }
