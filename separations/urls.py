from django.urls import path

from separations.views import (
    SeparationDetailView,
    SeparationListCreateView,
    SeparationStepDoneView,
    SeparationStepUndoView,
)

urlpatterns = [
    path("separations/", SeparationListCreateView.as_view(), name="separation-list-create"),
    path(
        "separations/<str:sep_id>/", SeparationDetailView.as_view(), name="separation-detail"
    ),
    path(
        "separations/<str:sep_id>/steps/<str:step_id>/done/",
        SeparationStepDoneView.as_view(),
        name="separation-step-done",
    ),
    path(
        "separations/<str:sep_id>/steps/<str:step_id>/undo/",
        SeparationStepUndoView.as_view(),
        name="separation-step-undo",
    ),
]
