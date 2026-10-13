"""Audit trail (Phase 6).

Every lifecycle transition and step-status change is recorded from the backend
(never from the browser), so the history cannot be skipped or forged by the UI.

An audit failure must never break the business action it describes, so
write_audit swallows (and logs) its own errors.
"""

import logging

from django.utils import timezone

from lifecycle.mongo import get_audit_log_collection

logger = logging.getLogger(__name__)


def user_label(request):
    """Who performed the action: the JWT user's email, else name, else id."""
    user = getattr(request, "user", None)
    if not user:
        return "system"
    return (
        getattr(user, "email", None)
        or getattr(user, "name", None)
        or getattr(user, "id", None)
        or "system"
    )


def write_audit(entity_type, entity_id, action, from_value=None, to_value=None, request=None, extra=None):
    try:
        get_audit_log_collection().insert_one(
            {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "action": action,
                "from": from_value,
                "to": to_value,
                "extra": extra or {},
                "performed_by": user_label(request) if request is not None else "system",
                "at": timezone.now().isoformat(),
            }
        )
    except Exception:  # noqa: BLE001 - audit must never break the real action
        logger.exception("Could not write audit_log entry")
