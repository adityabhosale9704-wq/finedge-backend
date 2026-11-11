import os
import uuid

from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import get_candidates_collection
from database.queries import get_candidate_by_id
from doc_checklist.serializers import AdditionalDocsSerializer, DocRejectSerializer
from doc_checklist.services import snapshot_doc_checklist_for_candidate
from finedge_backend.storage import build_doc_url


def serialize_checklist(request, candidate):
    docs = candidate.get("doc_checklist", [])
    docs = [
        {**item, "file_url": build_doc_url(request, item.get("file_url", ""))}
        for item in docs
    ]
    done = len([d for d in docs if d["status"] == "Verified"])
    additional = candidate.get(
        "additional_docs", {"uan_number": "", "marital_status": "", "nominee_docs": []}
    )
    additional = dict(additional)
    additional["nominee_docs"] = [
        {**n, "file_url": build_doc_url(request, n.get("file_url", ""))}
        for n in additional.get("nominee_docs", [])
    ]
    from lifecycle.docs import required_docs_summary
    from lifecycle.transitions import candidate_transition_status

    summary = required_docs_summary(candidate)
    ready, blocked_reason = candidate_transition_status(candidate)
    return {
        "candidate_id": candidate["id"],
        "candidate_name": candidate.get("name", ""),
        "outcome": candidate.get("outcome"),
        "required_total_count": summary["required_total_count"],
        "required_uploaded_count": summary["required_uploaded_count"],
        "all_uploaded": summary["all_uploaded"],
        "ready_for_onboarding": ready,
        "onboarding_blocked_reason": "" if ready else blocked_reason,
        "onboarding_employee_id": candidate.get("onboarding_employee_id"),
        "stage": candidate.get("stage", ""),
        "frozen": candidate.get("frozen", False),
        "doc_checklist": docs,
        "verified_count": done,
        "total_count": len(docs),
        "all_verified": len(docs) > 0 and done == len(docs),
        "additional_docs": additional,
    }


class CandidateDocChecklistView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        snapshot_doc_checklist_for_candidate(cand_id)
        candidate = get_candidate_by_id(cand_id)
        return Response(serialize_checklist(request, candidate))


class DocChecklistItemVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, item_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        docs = candidate.get("doc_checklist", [])
        item = next((d for d in docs if d["id"] == item_id), None)
        if not item:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)

        previous_status = item.get("status")
        item["status"] = "Verified"
        item["rejection_reason"] = ""
        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"doc_checklist": docs}}
        )

        from lifecycle.audit import write_audit

        write_audit(
            "candidate", cand_id, "document_verified", previous_status, "Verified", request,
            {"document": item.get("doc_name", "")},
        )

        updated = get_candidate_by_id(cand_id)
        return Response(serialize_checklist(request, updated))


class DocChecklistItemRejectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id, item_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        docs = candidate.get("doc_checklist", [])
        item = next((d for d in docs if d["id"] == item_id), None)
        if not item:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DocRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item["status"] = "Rejected"
        item["rejection_reason"] = serializer.validated_data.get("reason", "")
        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"doc_checklist": docs}}
        )
        updated = get_candidate_by_id(cand_id)
        return Response(serialize_checklist(request, updated))


class DocChecklistItemUploadView(APIView):
    """HR uploads a document on the candidate's behalf (multipart: file).

    The file is stored under MEDIA_ROOT/candidate_docs/<candidate>/ and shows up in
    the Docs tab (docs-vault) through the candidate's checklist. A re-upload replaces
    the file and puts the item back to "Pending" verification.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, cand_id, item_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        if candidate.get("onboarding_employee_id"):
            return Response(
                {"detail": "This candidate has already moved to Onboarding."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        docs = candidate.get("doc_checklist", [])
        item = next((d for d in docs if d["id"] == item_id), None)
        if not item:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "A file is required."}, status=status.HTTP_400_BAD_REQUEST)
        if uploaded_file.size > 10 * 1024 * 1024:
            return Response(
                {"detail": "The file is too large (maximum 10 MB)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        safe_name = os.path.basename(uploaded_file.name)
        relative_path = f"candidate_docs/{cand_id}/{uuid.uuid4().hex}_{safe_name}"
        default_storage.save(relative_path, uploaded_file)

        previous_status = item.get("status")
        item["file_url"] = relative_path
        item["status"] = "Pending"
        item["rejection_reason"] = ""
        item["uploaded_at"] = timezone.now().isoformat()
        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"doc_checklist": docs}}
        )

        from lifecycle.audit import write_audit

        write_audit(
            "candidate", cand_id, "document_uploaded", previous_status, "Pending", request,
            {"document": item.get("doc_name", ""), "file": safe_name},
        )

        updated = get_candidate_by_id(cand_id)
        return Response(serialize_checklist(request, updated), status=status.HTTP_201_CREATED)


class AdditionalDocsUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdditionalDocsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            set_fields = {"additional_docs." + k: v for k, v in data.items()}
            get_candidates_collection().update_one({"id": cand_id}, {"$set": set_fields})

        updated = get_candidate_by_id(cand_id)
        return Response(serialize_checklist(request, updated))


class SendDocLinkView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        if not candidate:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        snapshot_doc_checklist_for_candidate(cand_id)
        upload_token = uuid.uuid4().hex
        get_candidates_collection().update_one(
            {"id": cand_id}, {"$set": {"upload_token": upload_token}}
        )
        return Response({"upload_token": upload_token})


# ---------- Public (unauthenticated, token-protected) endpoints ----------
# A simple shared-secret link, not a session — matches the manual's "send a
# link, no login required" flow. The candidate never gets an account.


def check_public_token(candidate, token):
    return bool(token) and candidate.get("upload_token") == token


class PublicDocChecklistView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        token = request.query_params.get("token")
        if not candidate or not check_public_token(candidate, token):
            return Response({"detail": "Invalid or expired link."}, status=status.HTTP_404_NOT_FOUND)

        payload = serialize_checklist(request, candidate)
        payload.pop("frozen", None)
        return Response(payload)


class PublicDocUploadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        token = request.query_params.get("token")
        if not candidate or not check_public_token(candidate, token):
            return Response({"detail": "Invalid or expired link."}, status=status.HTTP_404_NOT_FOUND)

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "A file is required."}, status=status.HTTP_400_BAD_REQUEST)

        item_id = request.data.get("item_id")
        nominee_doc_name = request.data.get("nominee_doc_name")
        if not item_id and not nominee_doc_name:
            return Response(
                {"detail": "item_id or nominee_doc_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        safe_name = os.path.basename(uploaded_file.name)
        stored_filename = f"{uuid.uuid4().hex}_{safe_name}"
        relative_path = f"candidate_docs/{cand_id}/{stored_filename}"
        default_storage.save(relative_path, uploaded_file)

        if item_id:
            docs = candidate.get("doc_checklist", [])
            item = next((d for d in docs if d["id"] == item_id), None)
            if not item:
                return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
            item["file_url"] = relative_path
            item["status"] = "Pending"
            item["rejection_reason"] = ""
            get_candidates_collection().update_one(
                {"id": cand_id}, {"$set": {"doc_checklist": docs}}
            )
        else:
            additional = candidate.get(
                "additional_docs", {"uan_number": "", "marital_status": "", "nominee_docs": []}
            )
            nominee_docs = additional.get("nominee_docs", [])
            existing = next((n for n in nominee_docs if n["doc_name"] == nominee_doc_name), None)
            if existing:
                existing["file_url"] = relative_path
            else:
                nominee_docs.append(
                    {"id": uuid.uuid4().hex, "doc_name": nominee_doc_name, "file_url": relative_path}
                )
            get_candidates_collection().update_one(
                {"id": cand_id}, {"$set": {"additional_docs.nominee_docs": nominee_docs}}
            )

        updated = get_candidate_by_id(cand_id)
        payload = serialize_checklist(request, updated)
        payload.pop("frozen", None)
        return Response(payload, status=status.HTTP_201_CREATED)


class PublicAdditionalInfoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def patch(self, request, cand_id):
        candidate = get_candidate_by_id(cand_id)
        token = request.query_params.get("token")
        if not candidate or not check_public_token(candidate, token):
            return Response({"detail": "Invalid or expired link."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdditionalDocsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            set_fields = {"additional_docs." + k: v for k, v in data.items()}
            get_candidates_collection().update_one({"id": cand_id}, {"$set": set_fields})

        updated = get_candidate_by_id(cand_id)
        payload = serialize_checklist(request, updated)
        payload.pop("frozen", None)
        return Response(payload)
