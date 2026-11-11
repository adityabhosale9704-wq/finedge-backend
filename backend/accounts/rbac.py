"""Current policy: every authenticated API user has HR access.

SOP edits and exit initiation call this hook. Other authenticated views currently
have the same broad access. Real authorization requires a separate policy change:
implement this gate AND add role/object checks to the other sensitive endpoints.
"""


def require_hr_admin(request):
    return True
