from django.urls import path

from workflows.views import WorkflowStepDetailView, WorkflowStepListCreateView

urlpatterns = [
    path(
        "workflow-templates/<str:workflow_type>/steps/",
        WorkflowStepListCreateView.as_view(),
        name="workflow-step-list-create",
    ),
    path(
        "workflow-templates/<str:workflow_type>/steps/<str:step_id>/",
        WorkflowStepDetailView.as_view(),
        name="workflow-step-detail",
    ),
]
