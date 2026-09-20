from datetime import date

from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from compliance.mongo import get_compliance_items_collection
from compliance.serializers import ComplianceItemSerializer


def get_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_compliance_items_collection().find_one({"_id": object_id})


def compute_status(next_due_date):
    days_left = (next_due_date - date.today()).days
    if days_left < 0:
        return "red"
    if days_left <= 30:
        return "amber"
    return "green"


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if hasattr(doc.get("next_due_date"), "isoformat"):
        next_due_date = doc["next_due_date"]
        doc["next_due_date"] = next_due_date.isoformat()
    else:
        next_due_date = date.fromisoformat(doc["next_due_date"])
    doc["status"] = compute_status(next_due_date)
    return doc


class ComplianceItemListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = [serialize(item) for item in get_compliance_items_collection().find()]
        items.sort(key=lambda item: item["next_due_date"])
        return Response(items)

    def post(self, request):
        serializer = ComplianceItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data["next_due_date"] = data["next_due_date"].isoformat()

        result = get_compliance_items_collection().insert_one(data)
        created = get_compliance_items_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class ComplianceItemDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        item = get_by_pk(pk)
        if not item:
            return Response({"detail": "Compliance item not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ComplianceItemSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "next_due_date" in data:
            data["next_due_date"] = data["next_due_date"].isoformat()

        if data:
            get_compliance_items_collection().update_one({"_id": item["_id"]}, {"$set": data})

        updated = get_compliance_items_collection().find_one({"_id": item["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        item = get_by_pk(pk)
        if not item:
            return Response({"detail": "Compliance item not found."}, status=status.HTTP_404_NOT_FOUND)

        get_compliance_items_collection().delete_one({"_id": item["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
