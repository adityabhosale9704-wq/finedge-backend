from database.collections import get_sop_templates_collection
from database.seeds import seed_if_empty


def list_steps(process_type, only_active=False):
    """Ordered SOP steps for a process type ("recruitment" / "onboarding" /
    "exit"). Seeds the collection on first use."""
    seed_if_empty()
    query = {"process_type": process_type}
    if only_active:
        query["active"] = True
    return list(get_sop_templates_collection().find(query).sort("step_no", 1))
