from django.urls import path

from workindia.views import (
    WorkIndiaImportView,
    WorkIndiaListView,
    WorkIndiaLogCallView,
    WorkIndiaPromoteView,
    WorkIndiaRemoveView,
    WorkIndiaSelectView,
)

urlpatterns = [
    path("workindia/import/", WorkIndiaImportView.as_view(), name="workindia-import"),
    path("workindia/", WorkIndiaListView.as_view(), name="workindia-list"),
    path(
        "workindia/<str:wi_id>/promote/",
        WorkIndiaPromoteView.as_view(),
        name="workindia-promote",
    ),
    path(
        "workindia/<str:wi_id>/select/",
        WorkIndiaSelectView.as_view(),
        name="workindia-select",
    ),
    path(
        "workindia/<str:wi_id>/log-call/",
        WorkIndiaLogCallView.as_view(),
        name="workindia-log-call",
    ),
    path(
        "workindia/<str:wi_id>/remove/",
        WorkIndiaRemoveView.as_view(),
        name="workindia-remove",
    ),
]
