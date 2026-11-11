from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import get_employees_collection, get_positions_collection
from database.queries import (
    build_employee_name_lookup,
    generate_next_sequential_id,
    get_employee_by_pk,
)
from positions.serializers import (
    PositionAssignSerializer,
    PositionCreateSerializer,
    PositionUpdateSerializer,
)
from positions.services import assign_employee_to_position, get_position_by_id, unassign_position


def serialize_position(doc, employee_name_lookup=None):
    current_employee_id = doc.get("current_employee_id")
    current_holder_name = None
    if current_employee_id:
        if employee_name_lookup is not None:
            current_holder_name = employee_name_lookup.get(current_employee_id)
        else:
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
        positions = list(get_positions_collection().find())
        employee_name_lookup = build_employee_name_lookup(
            p.get("current_employee_id") for p in positions if p.get("current_employee_id")
        )
        return Response(
            [serialize_position(p, employee_name_lookup) for p in positions]
        )

    def post(self, request):
        serializer = PositionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        position_doc = {
            "id": generate_next_sequential_id(get_positions_collection(), "POS"),
            "designation": data["designation"],
            "department": data["department"],
            "branch": data["branch"],
            "status": "Vacant",
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

        assign_employee_to_position(position, employee)

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

        if position.get("status") != "Active" or not position.get("current_employee_id"):
            return Response(
                {"detail": "This position is not currently assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unassign_position(position)

        updated = get_position_by_id(pos_id)
        return Response(serialize_position(updated))
