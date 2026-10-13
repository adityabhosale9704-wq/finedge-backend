"""Seed / migrate SOP templates (Phase 1). Re-runnable, with a dry-run mode.

What it does: if the `sop_templates` collection is EMPTY, it creates the SOP
steps for recruitment, onboarding and exit, taking them from the existing
`workflow_templates` (Admin Studio "Workflows & TATs") when those exist, else
from built-in defaults. If sop_templates already has any data it does nothing.
It never modifies or deletes workflow_templates, candidates, employees or
separations (those already hold their own copies of their steps).

The API also seeds lazily on first use, so running this is optional; it is
useful to preview what would be created.

Usage (from the project root, venv active):
    python scripts/seed_sop_templates.py --dry-run     # preview only, writes nothing
    python scripts/seed_sop_templates.py               # actually seed
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finedge_backend.settings")

import django  # noqa: E402

django.setup()

from sop.seed import seed_if_empty  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="show what would happen, write nothing")
    args = parser.parse_args()

    result = seed_if_empty(dry_run=args.dry_run)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
