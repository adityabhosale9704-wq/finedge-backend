from datetime import date, timedelta

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import get_employees_collection, get_tasks_collection
from database.queries import generate_next_sequential_id, get_employee_by_pk
from tasks.serializers import TaskCreateSerializer, TaskUpdateSerializer
from tasks.services import compute_task_status


def get_task_by_id(task_id):
    return get_tasks_collection().find_one({"id": task_id})


def serialize_task(doc):
    return {
        "id": doc["id"],
        "title": doc.get("title", ""),
        "department": doc.get("department", ""),
        "assigned_to": doc.get("assigned_to"),
        "assigned_to_name": doc.get("assigned_to_name", ""),
        "tat_days": doc.get("tat_days", 3),
        "assigned_date": doc.get("assigned_date", ""),
        "due_date": doc.get("due_date", ""),
        "done": doc.get("done", False),
        "done_date": doc.get("done_date"),
        "status": compute_task_status(doc),
    }


class TaskListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = {}
        assigned_to = request.query_params.get("assigned_to")
        if assigned_to:
            query["assigned_to"] = assigned_to

        branch = request.query_params.get("branch")
        if branch:
            branch_employee_ids = [
                str(e["_id"]) for e in get_employees_collection().find({"branch": branch}, {"_id": 1})
            ]
            query["assigned_to"] = {"$in": branch_employee_ids}

        tasks = get_tasks_collection().find(query)
        return Response([serialize_task(t) for t in tasks])

    def post(self, request):
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        employee = get_employee_by_pk(data["assigned_to"])
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        tat_days = data.get("tat_days", 3)
        assigned_date = date.today()
        due_date = assigned_date + timedelta(days=tat_days)

        task_doc = {
            "id": generate_next_sequential_id(get_tasks_collection(), "TASK"),
            "title": data["title"],
            "department": data["department"],
            "assigned_to": data["assigned_to"],
            "assigned_to_name": employee.get("name", ""),
            "tat_days": tat_days,
            "assigned_date": assigned_date.isoformat(),
            "due_date": due_date.isoformat(),
            "done": False,
            "done_date": None,
        }
        get_tasks_collection().insert_one(task_doc)
        return Response(serialize_task(task_doc), status=status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, task_id):
        task = get_task_by_id(task_id)
        if not task:
            return Response(
                {"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = TaskUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "assigned_to" in data:
            employee = get_employee_by_pk(data["assigned_to"])
            if not employee:
                return Response(
                    {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
                )
            data["assigned_to_name"] = employee.get("name", "")

        if "tat_days" in data:
            assigned_date = date.fromisoformat(task["assigned_date"])
            data["due_date"] = (
                assigned_date + timedelta(days=data["tat_days"])
            ).isoformat()

        if data:
            get_tasks_collection().update_one({"id": task_id}, {"$set": data})

        updated = get_task_by_id(task_id)
        return Response(serialize_task(updated))

    def delete(self, request, task_id):
        task = get_task_by_id(task_id)
        if not task:
            return Response(
                {"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_tasks_collection().delete_one({"id": task_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskDoneView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_task_by_id(task_id)
        if not task:
            return Response(
                {"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if task.get("done"):
            return Response(
                {"detail": "This task is already marked done."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        get_tasks_collection().update_one(
            {"id": task_id},
            {"$set": {"done": True, "done_date": date.today().isoformat()}},
        )

        updated = get_task_by_id(task_id)
        return Response(serialize_task(updated))


class TaskUndoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        task = get_task_by_id(task_id)
        if not task:
            return Response(
                {"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_tasks_collection().update_one(
            {"id": task_id}, {"$set": {"done": False, "done_date": None}}
        )

        updated = get_task_by_id(task_id)
        return Response(serialize_task(updated))
