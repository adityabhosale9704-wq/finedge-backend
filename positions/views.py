from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from employees.views import get_employee_by_pk
from positions.mongo import get_positions_collection
from positions.serializers import (
    PositionAssignSerializer,
    PositionCreateSerializer,
    PositionUpdateSerializer,
)


def generate_next_position_id():
    max_num = 0
    for doc in get_positions_collection().find({}, {"id": 1}):
        pos_id = doc.get("id", "")
        if pos_id.startswith("POS-"):
            try:
                max_num = max(max_num, int(pos_id.split("-", 1)[1]))
            except ValueError:
                continue
    return f"POS-{max_num + 1:04d}"


def get_position_by_id(pos_id):
    return get_positions_collection().find_one({"id": pos_id})


def serialize_position(doc):
    current_employee_id = doc.get("current_employee_id")
    current_holder_name = None
    if current_employee_id:
        employee = get_employee_by_pk(current_employee_id)
        if employee:
            current_holder_name = employee.get("name")

    return {
        "id": doc["id"],
        "designation": doc.get("designation", ""),
        "department": doc.get("department", ""),
        "branch": doc.get("branch", ""),
        "status": doc.get("status", "Vacant"),
        "current_employee_id": current_employee_id,
        "current_holder_name": current_holder_name,
        "created_at": doc.get("created_at", ""),
    }


class PositionListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        positions = get_positions_collection().find()
        return Response([serialize_position(p) for p in positions])

    def post(self, request):
        serializer = PositionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        position_doc = {
            "id": generate_next_position_id(),
            "designation": data["designation"],
            "department": data["department"],
            "branch": data["branch"],
            "status": data.get("status", "Vacant"),
            "current_employee_id": None,
            "created_at": timezone.now().isoformat(),
            "history": [],
        }
        get_positions_collection().insert_one(position_doc)
        return Response(serialize_position(position_doc), status=status.HTTP_201_CREATED)


class PositionDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pos_id):
        position = get_position_by_id(pos_id)
        if not position:
            return Response(
                {"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PositionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_positions_collection().update_one({"id": pos_id}, {"$set": data})

        updated = get_position_by_id(pos_id)
        return Response(serialize_position(updated))

    def delete(self, request, pos_id):
        position = get_position_by_id(pos_id)
        if not position:
            return Response(
                {"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND
            )

        current_employee_id = position.get("current_employee_id")
        if current_employee_id:
            employee = get_employee_by_pk(current_employee_id)
            if employee:
                get_employees_collection().update_one(
                    {"_id": employee["_id"]}, {"$unset": {"position_id": ""}}
                )

        get_positions_collection().delete_one({"id": pos_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


class PositionHistoryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pos_id):
        position = get_position_by_id(pos_id)
        if not position:
            return Response(
                {"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND
            )

        history = list(reversed(position.get("history", [])))
        return Response(history)


class PositionAssignView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pos_id):
        position = get_position_by_id(pos_id)
        if not position:
            return Response(
                {"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if position.get("status") == "Active" or position.get("current_employee_id"):
            return Response(
                {
                    "detail": "This position is already occupied. Unassign the current holder first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PositionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee_id = serializer.validated_data["employee_id"]

        employee = get_employee_by_pk(employee_id)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if employee.get("position_id"):
            return Response(
                {
                    "detail": "This employee already holds a position ("
                    + employee["position_id"]
                    + "). Unassign them first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = date.today().isoformat()
        history_entry = {
            "employee_id": employee_id,
            "employee_name": employee.get("name", ""),
            "start_date": today,
            "end_date": None,
        }

        get_positions_collection().update_one(
            {"id": pos_id},
            {
                "$set": {"current_employee_id": employee_id, "status": "Active"},
                "$push": {"history": history_entry},
            },
        )
        get_employees_collection().update_one(
            {"_id": employee["_id"]}, {"$set": {"position_id": pos_id}}
        )

        updated = get_position_by_id(pos_id)
        return Response(serialize_position(updated))


class PositionUnassignView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pos_id):
        position = get_position_by_id(pos_id)
        if not position:
            return Response(
                {"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND
            )

        current_employee_id = position.get("current_employee_id")
        if position.get("status") != "Active" or not current_employee_id:
            return Response(
                {"detail": "This position is not currently assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = date.today().isoformat()

        get_positions_collection().update_one(
            {"id": pos_id},
            {
                "$set": {
                    "current_employee_id": None,
                    "status": "Vacant",
                    "history.$[open].end_date": today,
                }
            },
            array_filters=[{"open.end_date": None}],
        )

        employee = get_employee_by_pk(current_employee_id)
        if employee:
            get_employees_collection().update_one(
                {"_id": employee["_id"]}, {"$unset": {"position_id": ""}}
            )

        updated = get_position_by_id(pos_id)
        return Response(serialize_position(updated))
