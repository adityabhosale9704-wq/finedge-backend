from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from database.collections import get_audit_log_collection

ENTITY_TYPES = {"candidate", "employee", "separation", "sop"}


class AuditHistoryView(APIView):
    """GET /api/v1/audit/<entity_type>/<entity_id>/ : newest first."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_type, entity_id):
        if entity_type not in ENTITY_TYPES:
            return Response({"detail": "Unknown entity type."}, status=status.HTTP_400_BAD_REQUEST)

        entries = (
            get_audit_log_collection()
            .find({"entity_type": entity_type, "entity_id": entity_id})
            .sort("at", -1)
            .limit(200)
        )
        return Response(
            [
                {
                    "action": e.get("action", ""),
                    "from": e.get("from"),
                    "to": e.get("to"),
                    "extra": e.get("extra", {}),
                    "performed_by": e.get("performed_by", ""),
                    "at": e.get("at", ""),
                }
                for e in entries
            ]
        )
