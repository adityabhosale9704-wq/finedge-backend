from django.urls import path

from policies.views import (
    PolicyAcceptanceStatsView,
    PolicyDetailView,
    PolicyListCreateView,
)

urlpatterns = [
    path("policies/", PolicyListCreateView.as_view(), name="policy-list-create"),
    path("policies/<str:pk>/", PolicyDetailView.as_view(), name="policy-detail"),
    path(
        "policies-acceptance-stats/",
        PolicyAcceptanceStatsView.as_view(),
        name="policy-acceptance-stats",
    ),
]
