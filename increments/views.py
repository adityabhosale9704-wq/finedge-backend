import uuid

from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from increments.mongo import get_incentive_structures_collection
from increments.serializers import (
    IncentiveStructureCreateSerializer,
    IncentiveStructureUpdateSerializer,
)


def get_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_incentive_structures_collection().find_one({"_id": object_id})


def with_slab_ids(slabs):
    result = []
    for slab in slabs:
        slab = dict(slab)
        slab.setdefault("id", uuid.uuid4().hex)
        result.append(slab)
    return result


def serialize_structure(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    doc.setdefault("slabs", [])
    doc.setdefault("bonus_threshold", 0)
    doc.setdefault("bonus_amount", 0)
    return doc


class IncentiveStructureListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        structures = get_incentive_structures_collection().find()
        return Response([serialize_structure(s) for s in structures])

    def post(self, request):
        serializer = IncentiveStructureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["slabs"] = with_slab_ids(data.get("slabs", []))

        result = get_incentive_structures_collection().insert_one(data)
        created = get_incentive_structures_collection().find_one({"_id": result.inserted_id})
        return Response(serialize_structure(created), status=status.HTTP_201_CREATED)


class IncentiveStructureDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        structure = get_by_pk(pk)
        if not structure:
            return Response(
                {"detail": "Incentive structure not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = IncentiveStructureUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "slabs" in data:
            data["slabs"] = with_slab_ids(data["slabs"])

        if data:
            get_incentive_structures_collection().update_one(
                {"_id": structure["_id"]}, {"$set": data}
            )

        updated = get_incentive_structures_collection().find_one({"_id": structure["_id"]})
        return Response(serialize_structure(updated))

    def delete(self, request, pk):
        structure = get_by_pk(pk)
        if not structure:
            return Response(
                {"detail": "Incentive structure not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        get_incentive_structures_collection().delete_one({"_id": structure["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
