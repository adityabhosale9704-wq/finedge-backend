from django.utils import timezone
from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from engagement.mongo import (
    get_activities_collection,
    get_contests_collection,
    get_suggestions_collection,
)
from engagement.serializers import ActivitySerializer, ContestSerializer, SuggestionSerializer


def get_by_pk(collection, pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return collection.find_one({"_id": object_id})


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    for key in ("period_start", "period_end"):
        if key in doc and hasattr(doc[key], "isoformat"):
            doc[key] = doc[key].isoformat()
    return doc


class ContestListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([serialize(c) for c in get_contests_collection().find()])

    def post(self, request):
        serializer = ContestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for key in ("period_start", "period_end"):
            if data.get(key) is not None:
                data[key] = data[key].isoformat()

        result = get_contests_collection().insert_one(data)
        created = get_contests_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class ContestDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        contest = get_by_pk(get_contests_collection(), pk)
        if not contest:
            return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ContestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for key in ("period_start", "period_end"):
            if key in data and data[key] is not None:
                data[key] = data[key].isoformat()

        if data:
            get_contests_collection().update_one({"_id": contest["_id"]}, {"$set": data})

        updated = get_contests_collection().find_one({"_id": contest["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        contest = get_by_pk(get_contests_collection(), pk)
        if not contest:
            return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)

        get_contests_collection().delete_one({"_id": contest["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class SuggestionListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([serialize(s) for s in get_suggestions_collection().find()])

    def post(self, request):
        serializer = SuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data["submitted_at"] = timezone.now().isoformat()

        result = get_suggestions_collection().insert_one(data)
        created = get_suggestions_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class SuggestionDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        suggestion = get_by_pk(get_suggestions_collection(), pk)
        if not suggestion:
            return Response(
                {"detail": "Suggestion not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = SuggestionSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_suggestions_collection().update_one(
                {"_id": suggestion["_id"]}, {"$set": data}
            )

        updated = get_suggestions_collection().find_one({"_id": suggestion["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        suggestion = get_by_pk(get_suggestions_collection(), pk)
        if not suggestion:
            return Response(
                {"detail": "Suggestion not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_suggestions_collection().delete_one({"_id": suggestion["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivityListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([serialize(a) for a in get_activities_collection().find()])

    def post(self, request):
        serializer = ActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_activities_collection().insert_one(dict(serializer.validated_data))
        created = get_activities_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class ActivityDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        activity = get_by_pk(get_activities_collection(), pk)
        if not activity:
            return Response({"detail": "Activity not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ActivitySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_activities_collection().update_one({"_id": activity["_id"]}, {"$set": data})

        updated = get_activities_collection().find_one({"_id": activity["_id"]})
        return Response(serialize(updated))

    def delete(self, request, pk):
        activity = get_by_pk(get_activities_collection(), pk)
        if not activity:
            return Response({"detail": "Activity not found."}, status=status.HTTP_404_NOT_FOUND)

        get_activities_collection().delete_one({"_id": activity["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
