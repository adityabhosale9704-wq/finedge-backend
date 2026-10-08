from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from employees.mongo import get_employees_collection
from policies.mongo import get_policies_collection
from policies.serializers import PolicySerializer


def get_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_policies_collection().find_one({"_id": object_id})


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


class PolicyListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([serialize(p) for p in get_policies_collection().find()])

    def post(self, request):
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_policies_collection().insert_one(dict(serializer.validated_data))
        created = get_policies_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class PolicyDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        policy = get_by_pk(pk)
        if not policy:
            return Response({"detail": "Policy not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PolicySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_policies_collection().update_one({"_id": policy["_id"]}, {"$set": data})

        updated = get_policies_collection().find_one({"_id": policy["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        policy = get_by_pk(pk)
        if not policy:
            return Response({"detail": "Policy not found."}, status=status.HTTP_404_NOT_FOUND)

        get_policies_collection().delete_one({"_id": policy["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyAcceptanceStatsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employees = list(get_employees_collection().find({"status": {"$ne": "Leaver"}}))
        total = len(employees)
        accepted = len([e for e in employees if e.get("policy_accepted")])
        percentage = round((accepted / total) * 100, 1) if total else 0
        return Response({"total": total, "accepted": accepted, "percentage": percentage})
