from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from interview_questions.mongo import get_interview_questions_collection
from interview_questions.serializers import InterviewQuestionSerializer


def get_by_pk(pk):
    try:
        object_id = ObjectId(pk)
    except (InvalidId, TypeError):
        return None
    return get_interview_questions_collection().find_one({"_id": object_id})


def serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


class InterviewQuestionListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = {}
        department = request.query_params.get("department")
        question_type = request.query_params.get("type")
        if department:
            query["department"] = department
        if question_type:
            query["type"] = question_type

        questions = [serialize(q) for q in get_interview_questions_collection().find(query)]
        return Response(questions)

    def post(self, request):
        payload = request.data
        question_texts = payload.get("question_texts")

        if question_texts is not None:
            if not isinstance(question_texts, list) or not question_texts:
                return Response(
                    {"detail": "question_texts must be a non-empty list."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            created = []
            for question_text in question_texts:
                serializer = InterviewQuestionSerializer(data={
                    "department": payload.get("department", ""),
                    "type": payload.get("type"),
                    "question_text": question_text,
                })
                serializer.is_valid(raise_exception=True)
                result = get_interview_questions_collection().insert_one(dict(serializer.validated_data))
                created.append(serialize(get_interview_questions_collection().find_one({"_id": result.inserted_id})))
            return Response(created, status=status.HTTP_201_CREATED)

        serializer = InterviewQuestionSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        result = get_interview_questions_collection().insert_one(dict(serializer.validated_data))
        created = get_interview_questions_collection().find_one({"_id": result.inserted_id})
        return Response(serialize(created), status=status.HTTP_201_CREATED)


class InterviewQuestionDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        question = get_by_pk(pk)
        if not question:
            return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

        get_interview_questions_collection().delete_one({"_id": question["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)
