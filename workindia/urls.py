from django.urls import path

from workindia.views import WorkIndiaImportView, WorkIndiaListView, WorkIndiaPromoteView

urlpatterns = [
    path("workindia/import/", WorkIndiaImportView.as_view(), name="workindia-import"),
    path("workindia/", WorkIndiaListView.as_view(), name="workindia-list"),
    path(
        "workindia/<str:wi_id>/promote/",
        WorkIndiaPromoteView.as_view(),
        name="workindia-promote",
    ),
]
