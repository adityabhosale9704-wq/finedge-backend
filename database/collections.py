"""Collection names are part of the existing data contract."""
from database.connection import get_database


def get_users_collection():
    return get_database()["users"]


def get_departments_collection():
    return get_database()["departments"]


def get_branches_collection():
    return get_database()["branches"]


def get_roles_collection():
    return get_database()["roles"]


def get_salary_structure_collection():
    return get_database()["salary_structure"]


def get_salary_revisions_collection():
    return get_database()["salary_revisions"]


def get_compliance_items_collection():
    return get_database()["compliance_items"]


def get_employees_collection():
    return get_database()["employees"]


def get_contests_collection():
    return get_database()["contests"]


def get_suggestions_collection():
    return get_database()["suggestions"]


def get_activities_collection():
    return get_database()["activities"]


def get_incentive_structures_collection():
    return get_database()["incentive_structures"]


def get_interview_questions_collection():
    return get_database()["interview_questions"]


def get_letter_templates_collection():
    return get_database()["letter_templates"]


def get_audit_log_collection():
    return get_database()["audit_log"]


def get_policies_collection():
    return get_database()["policies"]


def get_positions_collection():
    return get_database()["positions"]


def get_requisitions_collection():
    return get_database()["requisitions"]


def get_candidates_collection():
    return get_database()["candidates"]


def get_reference_checks_collection():
    return get_database()["reference_checks"]


def get_separations_collection():
    return get_database()["separations"]


def get_sop_templates_collection():
    return get_database()["sop_templates"]


def get_tasks_collection():
    return get_database()["tasks"]


def get_workflow_templates_collection():
    return get_database()["workflow_templates"]


def get_workindia_collection():
    return get_database()["workindia_candidates"]
