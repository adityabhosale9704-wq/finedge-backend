from django.urls import path

from lifecycle.views import AuditHistoryView

urlpatterns = [
    path("<str:entity_type>/<str:entity_id>/", AuditHistoryView.as_view(), name="audit-history"),
]
