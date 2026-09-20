from django.urls import path

from compliance.views import ComplianceItemDetailView, ComplianceItemListCreateView

urlpatterns = [
    path(
        "compliance/",
        ComplianceItemListCreateView.as_view(),
        name="compliance-list-create",
    ),
    path(
        "compliance/<str:pk>/",
        ComplianceItemDetailView.as_view(),
        name="compliance-detail",
    ),
]
