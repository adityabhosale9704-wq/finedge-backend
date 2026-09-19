from django.urls import path

from admin_studio.views import (
    BranchDetailView,
    BranchListCreateView,
    DepartmentDetailView,
    DepartmentListCreateView,
)

urlpatterns = [
    path(
        "departments/",
        DepartmentListCreateView.as_view(),
        name="department-list-create",
    ),
    path(
        "departments/<str:pk>/",
        DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path("branches/", BranchListCreateView.as_view(), name="branch-list-create"),
    path("branches/<str:pk>/", BranchDetailView.as_view(), name="branch-detail"),
]
