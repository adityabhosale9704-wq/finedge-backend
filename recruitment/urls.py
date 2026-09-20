from django.urls import path

from recruitment.views import (
    CandidateCreateEmployeeView,
    CandidateDetailView,
    CandidateListCreateView,
    CandidateStepDoneView,
    CandidateStepUndoView,
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
    path(
        "candidates/<str:cand_id>/steps/<str:step_id>/done/",
        CandidateStepDoneView.as_view(),
        name="candidate-step-done",
    ),
    path(
        "candidates/<str:cand_id>/steps/<str:step_id>/undo/",
        CandidateStepUndoView.as_view(),
        name="candidate-step-undo",
    ),
    path(
        "candidates/<str:cand_id>/create-employee/",
        CandidateCreateEmployeeView.as_view(),
        name="candidate-create-employee",
    ),
]
