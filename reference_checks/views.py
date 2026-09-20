from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from recruitment.views import get_candidate_by_id
from reference_checks.mongo import get_reference_checks_collection
from reference_checks.serializers import (
    ReferenceCheckSerializer,
    ReferenceCheckUpdateSerializer,
)


def get_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_reference_checks_collection().find_one({"_id": object_id})


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


class ReferenceCheckListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = {}
        candidate_id = request.query_params.get("candidate_id")
        if candidate_id:
            query["candidate_id"] = candidate_id

        checks = [serialize(c) for c in get_reference_checks_collection().find(query)]
        return Response(checks)

    def post(self, request):
        serializer = ReferenceCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_reference_checks_collection().insert_one(dict(serializer.validated_data))
        created = get_reference_checks_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class ReferenceCheckDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        check = get_by_pk(pk)
        if not check:
            return Response({"detail": "Reference check not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReferenceCheckUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_reference_checks_collection().update_one({"_id": check["_id"]}, {"$set": data})

        updated = get_reference_checks_collection().find_one({"_id": check["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        check = get_by_pk(pk)
        if not check:
            return Response({"detail": "Reference check not found."}, status=status.HTTP_404_NOT_FOUND)

        get_reference_checks_collection().delete_one({"_id": check["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateCanIssueAppointmentLetterView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        positive_count = get_reference_checks_collection().count_documents(
            {"candidate_id": cand_id, "status": "Positive"}
        )
        return Response({"can_issue": positive_count >= 2, "positive_count": positive_count})
