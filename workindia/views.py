import csv
import io
import re

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from recruitment.mongo import get_candidates_collection
from recruitment.views import generate_next_sequential_id, get_requisition_by_id
from workflows.views import snapshot_steps_for_instance
from workindia.mongo import get_workindia_collection
from workindia.serializers import WorkIndiaLogCallSerializer, WorkIndiaPromoteSerializer

FIELD_KEYS = [
    "full_name",
    "mobile",
    "city",
    "location",
    "qualification",
    "experience_level",
    "relevant_experience",
    "gender",
    "resume_url",
    "skills",
    "current_salary",
    "age",
    "specialization",
    "previous_designation",
    "previous_company",
]

COLUMN_ALIASES = {
    "full name": "full_name",
    "name": "full_name",
    "mobile no": "mobile",
    "mobile number": "mobile",
    "mobile": "mobile",
    "phone": "mobile",
    "city": "city",
    "location": "location",
    "qualification": "qualification",
    "level of experience": "experience_level",
    "experience level": "experience_level",
    "relevant experience": "relevant_experience",
    "gender": "gender",
    "resume link": "resume_url",
    "resume url": "resume_url",
    "skills": "skills",
    "current salary": "current_salary",
    "age": "age",
    "specialization": "specialization",
    "previous designation": "previous_designation",
    "previous company name": "previous_company",
    "previous company": "previous_company",
}


def normalize_header(header):
    return re.sub(r"[^a-z0-9]+", " ", header.strip().lower()).strip()


def serialize_workindia(doc):
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def get_workindia_by_id(wi_id):
    return get_workindia_collection().find_one({"id": wi_id})


class WorkIndiaImportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "A CSV file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw_text = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"detail": "Could not read the file. Please upload a UTF-8 encoded CSV."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(raw_text))
        if not reader.fieldnames:
            return Response(
                {"detail": "The CSV file appears to be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        header_map = {}
        for header in reader.fieldnames:
            field_key = COLUMN_ALIASES.get(normalize_header(header))
            if field_key:
                header_map[header] = field_key

        parsed_rows = []
        for row in reader:
            doc = {field: "" for field in FIELD_KEYS}
            for original_header, field_key in header_map.items():
                value = row.get(original_header)
                if value:
                    doc[field_key] = value.strip()

            if any(doc.values()):
                parsed_rows.append(doc)

        collection = get_workindia_collection()
        max_num = 0
        for existing in collection.find({}, {"id": 1}):
            value = existing.get("id", "")
            if value.startswith("WI-"):
                try:
                    max_num = max(max_num, int(value.split("-", 1)[1]))
                except ValueError:
                    continue

        now = timezone.now().isoformat()
        for index, doc in enumerate(parsed_rows):
            doc["id"] = f"WI-{max_num + index + 1:04d}"
            doc["imported_at"] = now
            doc["promoted"] = False
            doc["stage"] = "Uploaded"
            doc["excluded"] = False
            doc["call_status"] = ""
            doc["call_notes"] = ""
            doc["interview_datetime"] = None

        if parsed_rows:
            collection.insert_many(parsed_rows)

        return Response(
            {"imported": len(parsed_rows)}, status=status.HTTP_201_CREATED
        )


class WorkIndiaListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = {}

        promoted_param = request.query_params.get("promoted")
        if promoted_param is not None:
            query["promoted"] = promoted_param.lower() == "true"

        stage_param = request.query_params.get("stage")
        if stage_param:
            query["stage"] = stage_param

        include_excluded = request.query_params.get("include_excluded", "false").lower() == "true"
        if not include_excluded:
            query["excluded"] = {"$ne": True}

        search_term = request.query_params.get("q")
        if search_term:
            regex = {"$regex": re.escape(search_term), "$options": "i"}
            query["$or"] = [
                {"full_name": regex},
                {"city": regex},
                {"skills": regex},
            ]

        candidates = get_workindia_collection().find(query)
        return Response([serialize_workindia(c) for c in candidates])


class WorkIndiaPromoteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, wi_id):
        workindia_candidate = get_workindia_by_id(wi_id)
        if not workindia_candidate:
            return Response(
                {"detail": "WorkIndia candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if workindia_candidate.get("promoted"):
            return Response(
                {"detail": "This candidate has already been promoted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WorkIndiaPromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requisition_id = serializer.validated_data["requisition_id"]

        if not get_requisition_by_id(requisition_id):
            return Response(
                {"detail": "Requisition not found."}, status=status.HTTP_404_NOT_FOUND
            )

        candidate_doc = {
            "id": generate_next_sequential_id(get_candidates_collection(), "CAND"),
            "name": workindia_candidate.get("full_name", ""),
            "phone": workindia_candidate.get("mobile", ""),
            "email": "",
            "requisition_id": requisition_id,
            "source": "WorkIndia",
            "experience": workindia_candidate.get("relevant_experience", ""),
            "stage": "Applied",
            "steps": snapshot_steps_for_instance("Recruitment"),
            "created_at": timezone.now().isoformat(),
        }
        get_candidates_collection().insert_one(candidate_doc)

        get_workindia_collection().update_one(
            {"id": wi_id}, {"$set": {"promoted": True}}
        )

        updated = get_workindia_by_id(wi_id)
        return Response(serialize_workindia(updated))


class WorkIndiaSelectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, wi_id):
        workindia_candidate = get_workindia_by_id(wi_id)
        if not workindia_candidate:
            return Response(
                {"detail": "WorkIndia candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        get_workindia_collection().update_one(
            {"id": wi_id}, {"$set": {"stage": "Selected"}}
        )
        updated = get_workindia_by_id(wi_id)
        return Response(serialize_workindia(updated))


class WorkIndiaLogCallView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, wi_id):
        workindia_candidate = get_workindia_by_id(wi_id)
        if not workindia_candidate:
            return Response(
                {"detail": "WorkIndia candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WorkIndiaLogCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if data.get("interview_datetime") is not None:
            data["interview_datetime"] = data["interview_datetime"].isoformat()
        data["stage"] = "Called"

        get_workindia_collection().update_one({"id": wi_id}, {"$set": data})
        updated = get_workindia_by_id(wi_id)
        return Response(serialize_workindia(updated))


class WorkIndiaRemoveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, wi_id):
        workindia_candidate = get_workindia_by_id(wi_id)
        if not workindia_candidate:
            return Response(
                {"detail": "WorkIndia candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        get_workindia_collection().update_one(
            {"id": wi_id}, {"$set": {"excluded": True}}
        )
        updated = get_workindia_by_id(wi_id)
        return Response(serialize_workindia(updated))
