from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from recruitment.mongo import get_candidates_collection
from separations.mongo import get_separations_collection

CANDIDATE_TERMINAL_STAGES = {"Joined", "Rejected", "Withdrawn"}


def first_undone_step(steps):
    for step in steps or []:
        if not step.get("done"):
            return step
    return None


class DoneBoardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = []

        for candidate in get_candidates_collection().find():
            if candidate.get("stage") in CANDIDATE_TERMINAL_STAGES:
                continue
            step = first_undone_step(candidate.get("steps"))
            if step:
                items.append({
                    "module": "recruitment",
                    "person_name": candidate.get("name"),
                    "record_id": candidate.get("id"),
                    "step_id": step.get("id"),
                    "step_name": step.get("step_name"),
                    "who": step.get("who"),
                })

        for employee in get_employees_collection().find({"status": "Onboarding"}):
            step = first_undone_step(employee.get("onboarding_steps"))
            if step:
                items.append({
                    "module": "onboarding",
                    "person_name": employee.get("name"),
                    "record_id": employee.get("id"),
                    "step_id": step.get("id"),
                    "step_name": step.get("step_name"),
                    "who": step.get("who"),
                })

        for separation in get_separations_collection().find():
            steps = separation.get("steps", [])
            done_count = sum(1 for s in steps if s.get("done"))
            is_complete = len(steps) > 0 and done_count == len(steps)
            if is_complete:
                continue
            step = first_undone_step(steps)
            if step:
                employee = get_employees_collection().find_one({"id": separation.get("employee_id")})
                items.append({
                    "module": "exit",
                    "person_name": employee.get("name") if employee else separation.get("employee_id"),
                    "record_id": separation.get("id"),
                    "step_id": step.get("id"),
                    "step_name": step.get("step_name"),
                    "who": step.get("who"),
                })

        return Response(items)
