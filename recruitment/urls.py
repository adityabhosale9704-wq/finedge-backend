from django.urls import path

from recruitment.views import (
    CandidateDetailView,
    CandidateListCreateView,
    RequisitionApproveView,
    RequisitionDetailView,
    RequisitionListCreateView,
)

urlpatterns = [
    path(
        "requisitions/",
        RequisitionListCreateView.as_view(),
        name="requisition-list-create",
    ),
    path(
        "requisitions/<str:req_id>/",
        RequisitionDetailView.as_view(),
        name="requisition-detail",
    ),
    path(
        "requisitions/<str:req_id>/approve/",
        RequisitionApproveView.as_view(),
        name="requisition-approve",
    ),
    path(
        "candidates/", CandidateListCreateView.as_view(), name="candidate-list-create"
    ),
    path(
        "candidates/<str:cand_id>/",
        CandidateDetailView.as_view(),
        name="candidate-detail",
    ),
]
