from django.urls import path

from engagement.views import (
    ActivityDetailView,
    ActivityListCreateView,
    ContestDetailView,
    ContestListCreateView,
    SuggestionDetailView,
    SuggestionListCreateView,
)

urlpatterns = [
    path(
        "engagement/contests/",
        ContestListCreateView.as_view(),
        name="contest-list-create",
    ),
    path(
        "engagement/contests/<str:pk>/",
        ContestDetailView.as_view(),
        name="contest-detail",
    ),
    path(
        "engagement/suggestions/",
        SuggestionListCreateView.as_view(),
        name="suggestion-list-create",
    ),
    path(
        "engagement/suggestions/<str:pk>/",
        SuggestionDetailView.as_view(),
        name="suggestion-detail",
    ),
    path(
        "engagement/activities/",
        ActivityListCreateView.as_view(),
        name="activity-list-create",
    ),
    path(
        "engagement/activities/<str:pk>/",
        ActivityDetailView.as_view(),
        name="activity-detail",
    ),
]
