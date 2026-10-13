"""Single place for role checks on sensitive HR actions.

RBAC is intentionally NOT enforced yet: every authenticated user is treated as
an HR Admin. Sensitive views (SOP edits, exit initiation, lifecycle moves, ...)
all call require_hr_admin(request), so when roles are introduced only this
function has to change, e.g. to raise rest_framework.exceptions.PermissionDenied
when request.user.role is not an HR role.
"""


def require_hr_admin(request):
    return True
