from django.urls import path

from reference_checks.views import (
    CandidateCanIssueAppointmentLetterView,
    ReferenceCheckDetailView,
    ReferenceCheckListCreateView,
)

urlpatterns = [
    path(
        "reference-checks/",
        ReferenceCheckListCreateView.as_view(),
        name="reference-check-list-create",
    ),
    path(
        "reference-checks/<str:pk>/",
        ReferenceCheckDetailView.as_view(),
        name="reference-check-detail",
    ),
    path(
        "candidates/<str:cand_id>/can-issue-appointment-letter/",
        CandidateCanIssueAppointmentLetterView.as_view(),
        name="candidate-can-issue-appointment-letter",
    ),
]
