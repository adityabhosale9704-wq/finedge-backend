from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from compliance.mongo import get_compliance_items_collection
from compliance.views import compute_status
from done_board.views import DoneBoardView
from tasks.mongo import get_tasks_collection
from tasks.views import compute_task_status

DONE_BOARD_PAGE_BY_MODULE = {
    "recruitment": "recruitment.html",
    "onboarding": "onboarding.html",
    "exit": "exit.html",
}


class NotificationsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = []

        # Reuses Done Board's own aggregation logic rather than duplicating it.
        done_board_items = DoneBoardView().get(request).data
        for item in done_board_items:
            items.append({
                "type": "pending_step",
                "message": item["person_name"] + " — " + item["step_name"],
                "page": DONE_BOARD_PAGE_BY_MODULE.get(item["module"], "done-board.html"),
            })

        for task in get_tasks_collection().find():
            if task.get("done"):
                continue
            status_value = compute_task_status(task)
            if status_value == "Overdue":
                items.append({
                    "type": "overdue_task",
                    "message": "Overdue: " + task.get("title", ""),
                    "page": "tasks.html",
                })

        for item in get_compliance_items_collection().find():
            next_due_date = date.fromisoformat(item["next_due_date"])
            status_value = compute_status(next_due_date)
            if status_value in ("amber", "red"):
                items.append({
                    "type": "compliance",
                    "message": item.get("act_name", "") + " due " + item["next_due_date"],
                    "page": "compliance.html",
                })

        return Response({"count": len(items), "items": items})
