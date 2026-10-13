from django.urls import path

from sop.views import SopStepDetailView, SopStepListCreateView, SopStepReorderView

urlpatterns = [
    path("steps/<str:step_id>/", SopStepDetailView.as_view(), name="sop-step-detail"),
    path("<str:process_type>/steps/", SopStepListCreateView.as_view(), name="sop-step-list-create"),
    path("<str:process_type>/steps/reorder/", SopStepReorderView.as_view(), name="sop-step-reorder"),
]
