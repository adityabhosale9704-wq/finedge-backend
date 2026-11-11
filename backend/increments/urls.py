from django.urls import path

from increments.views import (
    IncentiveStructureDetailView,
    IncentiveStructureListCreateView,
)

urlpatterns = [
    path(
        "incentive-structures/",
        IncentiveStructureListCreateView.as_view(),
        name="incentive-structure-list-create",
    ),
    path(
        "incentive-structures/<str:pk>/",
        IncentiveStructureDetailView.as_view(),
        name="incentive-structure-detail",
    ),
]
