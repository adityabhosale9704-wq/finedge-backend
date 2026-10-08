from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from letter_templates.mongo import get_letter_templates_collection
from letter_templates.serializers import LETTER_TYPES, LetterTemplateSerializer

DEFAULT_BODIES = {
    "Offer Letter": (
        "Dear {{name}},\n\n"
        "We are pleased to offer you the position of {{designation}} in the {{department}} "
        "department at our {{branch}} location, effective {{doj}}. Your annual CTC will be "
        "{{ctc}}, as detailed in the salary annexure below.\n\n"
        "This offer is subject to a probation period of {{probation}} from your date of "
        "joining, during which your performance and conduct will be reviewed.\n\n"
        "We look forward to welcoming you to the team. Please sign and return a copy of "
        "this letter to confirm your acceptance."
    ),
    "Appointment Letter": (
        "Dear {{name}},\n\n"
        "Further to your offer of employment, we are pleased to confirm your appointment "
        "as {{designation}} in the {{department}} department at our {{branch}} location, "
        "with effect from {{doj}}.\n\n"
        "Your annual CTC has been fixed at {{ctc}}, as per the salary annexure enclosed "
        "with this letter. Your appointment is subject to a probation period of "
        "{{probation}}.\n\n"
        "We trust you will find your role challenging and rewarding, and we look forward "
        "to a long and successful association."
    ),
    "Confirmation Letter": (
        "Dear {{name}},\n\n"
        "We are pleased to inform you that, based on a satisfactory review of your "
        "performance and conduct during your probation period, your employment as "
        "{{designation}} in the {{department}} department at our {{branch}} location "
        "stands confirmed with effect from today.\n\n"
        "Your annual CTC continues at {{ctc}}, as per the enclosed salary annexure. All "
        "other terms of your employment remain unchanged.\n\n"
        "We congratulate you on your confirmation and look forward to your continued "
        "contribution to the organization."
    ),
    "Increment Letter": (
        "Dear {{name}},\n\n"
        "We are pleased to inform you that, in recognition of your performance and "
        "contribution as {{designation}} in the {{department}} department at our "
        "{{branch}} location, your annual CTC has been revised to {{ctc}}, effective "
        "from today.\n\n"
        "The revised salary annexure is enclosed below for your reference.\n\n"
        "We appreciate your continued dedication and look forward to your ongoing "
        "success with the organization."
    ),
    "Relieving-cum-Experience Letter": (
        "Dear {{name}},\n\n"
        "This is to certify that you were employed with us as {{designation}} in the "
        "{{department}} department at our {{branch}} location from {{doj}} until your "
        "last working day.\n\n"
        "During your tenure, your annual CTC was {{ctc}}. We found your conduct and "
        "performance to be satisfactory during your association with us.\n\n"
        "We wish you the very best in your future endeavors."
    ),
}


def get_or_create_template(letter_type):
    collection = get_letter_templates_collection()
    doc = collection.find_one({"letter_type": letter_type})
    if doc:
        return doc

    doc = {
        "letter_type": letter_type,
        "subject": letter_type,
        "body": DEFAULT_BODIES.get(letter_type, ""),
    }
    collection.insert_one(doc)
    return doc


def serialize(doc):
    return {
        "letter_type": doc["letter_type"],
        "subject": doc.get("subject", ""),
        "body": doc.get("body", ""),
    }


class LetterTemplateListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([serialize(get_or_create_template(t)) for t in LETTER_TYPES])


class LetterTemplateDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, letter_type):
        if letter_type not in LETTER_TYPES:
            return Response({"detail": "Unknown letter type."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize(get_or_create_template(letter_type)))

    def patch(self, request, letter_type):
        if letter_type not in LETTER_TYPES:
            return Response({"detail": "Unknown letter type."}, status=status.HTTP_404_NOT_FOUND)

        get_or_create_template(letter_type)

        serializer = LetterTemplateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data:
            get_letter_templates_collection().update_one(
                {"letter_type": letter_type}, {"$set": data}
            )

        updated = get_letter_templates_collection().find_one({"letter_type": letter_type})
        return Response(serialize(updated))
