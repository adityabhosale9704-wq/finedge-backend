from django.urls import path

from doc_checklist.views import (
    AdditionalDocsUpdateView,
    CandidateDocChecklistView,
    DocChecklistItemRejectView,
    DocChecklistItemVerifyView,
    PublicAdditionalInfoView,
    PublicDocChecklistView,
    PublicDocUploadView,
    SendDocLinkView,
)

urlpatterns = [
    path(
        "candidates/<str:cand_id>/doc-checklist/",
        CandidateDocChecklistView.as_view(),
        name="candidate-doc-checklist",
    ),
    path(
        "candidates/<str:cand_id>/doc-checklist/<str:item_id>/verify/",
        DocChecklistItemVerifyView.as_view(),
        name="doc-checklist-item-verify",
    ),
    path(
        "candidates/<str:cand_id>/doc-checklist/<str:item_id>/reject/",
        DocChecklistItemRejectView.as_view(),
        name="doc-checklist-item-reject",
    ),
    path(
        "candidates/<str:cand_id>/additional-docs/",
        AdditionalDocsUpdateView.as_view(),
        name="additional-docs-update",
    ),
    path(
        "candidates/<str:cand_id>/send-doc-link/",
        SendDocLinkView.as_view(),
        name="send-doc-link",
    ),
    path(
        "candidates/<str:cand_id>/public-checklist/",
        PublicDocChecklistView.as_view(),
        name="public-doc-checklist",
    ),
    path(
        "candidates/<str:cand_id>/public-upload/",
        PublicDocUploadView.as_view(),
        name="public-doc-upload",
    ),
    path(
        "candidates/<str:cand_id>/public-additional-info/",
        PublicAdditionalInfoView.as_view(),
        name="public-additional-info",
    ),
]
