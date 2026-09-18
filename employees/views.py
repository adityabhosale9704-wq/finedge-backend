from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from employees.serializers import EmployeeSerializer


def serialize_employee(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if "date_of_joining" in doc and hasattr(doc["date_of_joining"], "isoformat"):
        doc["date_of_joining"] = doc["date_of_joining"].isoformat()
    return doc


class EmployeeListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees = get_employees_collection().find()
        return Response([serialize_employee(e) for e in employees])

    def post(self, request):
        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data["date_of_joining"] = data["date_of_joining"].isoformat()

        result = get_employees_collection().insert_one(data)
        created = get_employees_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_employee(created), status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            object_id = ObjectId(pk)
        except (InvalidId, TypeError):
            return None
        return get_employees_collection().find_one({"_id": object_id})

    def get(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(serialize_employee(employee))

    def patch(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "date_of_joining" in data:
            data["date_of_joining"] = data["date_of_joining"].isoformat()

        if data:
            get_employees_collection().update_one(
                {"_id": employee["_id"]}, {"$set": data}
            )

        updated = get_employees_collection().find_one({"_id": employee["_id"]})
        return Response(serialize_employee(updated))

    def delete(self, request, pk):
        employee = self.get_object(pk)
        if not employee:
            return Response(
                {"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
            )
        get_employees_collection().delete_one({"_id": employee["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
