from django.urls import path

from compensation.views import (
    SalaryRevisionApproveView,
    SalaryRevisionListCreateView,
    SalaryRevisionRejectView,
    SalaryStructureView,
)

urlpatterns = [
    path("salary-structure/", SalaryStructureView.as_view(), name="salary-structure"),
    path(
        "salary-revisions/",
        SalaryRevisionListCreateView.as_view(),
        name="salary-revision-list-create",
    ),
    path(
        "salary-revisions/<str:rev_id>/approve/",
        SalaryRevisionApproveView.as_view(),
        name="salary-revision-approve",
    ),
    path(
        "salary-revisions/<str:rev_id>/reject/",
        SalaryRevisionRejectView.as_view(),
        name="salary-revision-reject",
    ),
]
