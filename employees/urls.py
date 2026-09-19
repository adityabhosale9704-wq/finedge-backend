from django.urls import path

from employees.views import (
    EmployeeDetailView,
    EmployeeDocumentDetailView,
    EmployeeDocumentListCreateView,
    EmployeeFacilityDetailView,
    EmployeeFacilityListCreateView,
    EmployeeFamilyDetailView,
    EmployeeFamilyListCreateView,
    EmployeeListCreateView,
)

urlpatterns = [
    path("", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("<str:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path(
        "<str:pk>/family/",
        EmployeeFamilyListCreateView.as_view(),
        name="employee-family-list-create",
    ),
    path(
        "<str:pk>/family/<str:family_id>/",
        EmployeeFamilyDetailView.as_view(),
        name="employee-family-detail",
    ),
    path(
        "<str:pk>/facilities/",
        EmployeeFacilityListCreateView.as_view(),
        name="employee-facility-list-create",
    ),
    path(
        "<str:pk>/facilities/<str:facility_id>/",
        EmployeeFacilityDetailView.as_view(),
        name="employee-facility-detail",
    ),
    path(
        "<str:pk>/documents/",
        EmployeeDocumentListCreateView.as_view(),
        name="employee-document-list-create",
    ),
    path(
        "<str:pk>/documents/<str:doc_id>/",
        EmployeeDocumentDetailView.as_view(),
        name="employee-document-detail",
    ),
]
