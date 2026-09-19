from django.urls import path

from positions.views import (
    PositionAssignView,
    PositionDetailView,
    PositionHistoryView,
    PositionListCreateView,
    PositionUnassignView,
)

urlpatterns = [
    path("", PositionListCreateView.as_view(), name="position-list-create"),
    path("<str:pos_id>/", PositionDetailView.as_view(), name="position-detail"),
    path(
        "<str:pos_id>/history/",
        PositionHistoryView.as_view(),
        name="position-history",
    ),
    path(
        "<str:pos_id>/assign/", PositionAssignView.as_view(), name="position-assign"
    ),
    path(
        "<str:pos_id>/unassign/",
        PositionUnassignView.as_view(),
        name="position-unassign",
    ),
]
