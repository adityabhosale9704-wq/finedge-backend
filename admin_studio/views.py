from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from admin_studio.mongo import (
    get_branches_collection,
    get_departments_collection,
    get_roles_collection,
)
from admin_studio.serializers import BranchSerializer, DepartmentSerializer, RoleSerializer


def serialize_master(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def serialize_branch(doc):
    doc = serialize_master(doc)
    doc.setdefault("s_and_e_number", "")
    return doc


def serialize_role(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    doc["department_id"] = str(doc["department_id"])
    return doc


def get_by_pk(collection, pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return collection.find_one({"_id": object_id})


class DepartmentListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        departments = get_departments_collection().find()
        return Response([serialize_master(d) for d in departments])

    def post(self, request):
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_departments_collection().insert_one(dict(serializer.validated_data))
        created = get_departments_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_master(created), status=status.HTTP_201_CREATED)


class DepartmentDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        department = get_by_pk(get_departments_collection(), pk)
        if not department:
            return Response(
                {"detail": "Department not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = DepartmentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_departments_collection().update_one(
                {"_id": department["_id"]}, {"$set": data}
            )

        updated = get_departments_collection().find_one({"_id": department["_id"]})
        return Response(serialize_master(updated))

    def delete(self, request, pk):
        department = get_by_pk(get_departments_collection(), pk)
        if not department:
            return Response(
                {"detail": "Department not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_departments_collection().delete_one({"_id": department["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branches = get_branches_collection().find()
        return Response([serialize_branch(b) for b in branches])

    def post(self, request):
        serializer = BranchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_branches_collection().insert_one(dict(serializer.validated_data))
        created = get_branches_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_branch(created), status=status.HTTP_201_CREATED)


class BranchDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        branch = get_by_pk(get_branches_collection(), pk)
        if not branch:
            return Response(
                {"detail": "Branch not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = BranchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_branches_collection().update_one({"_id": branch["_id"]}, {"$set": data})

        updated = get_branches_collection().find_one({"_id": branch["_id"]})
        return Response(serialize_branch(updated))

    def delete(self, request, pk):
        branch = get_by_pk(get_branches_collection(), pk)
        if not branch:
            return Response(
                {"detail": "Branch not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_branches_collection().delete_one({"_id": branch["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoleListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, department_id):
        department = get_by_pk(get_departments_collection(), department_id)
        if not department:
            return Response(
                {"detail": "Department not found."}, status=status.HTTP_404_NOT_FOUND
            )

        roles = get_roles_collection().find({"department_id": department["_id"]})
        return Response([serialize_role(r) for r in roles])

    def post(self, request, department_id):
        department = get_by_pk(get_departments_collection(), department_id)
        if not department:
            return Response(
                {"detail": "Department not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["department_id"] = department["_id"]

        result = get_roles_collection().insert_one(data)
        created = get_roles_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_role(created), status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        role = get_by_pk(get_roles_collection(), pk)
        if not role:
            return Response(
                {"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoleSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_roles_collection().update_one({"_id": role["_id"]}, {"$set": data})

        updated = get_roles_collection().find_one({"_id": role["_id"]})
        return Response(serialize_role(updated))

    def delete(self, request, pk):
        role = get_by_pk(get_roles_collection(), pk)
        if not role:
            return Response(
                {"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_roles_collection().delete_one({"_id": role["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
