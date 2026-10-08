from django.urls import path

from letter_templates.views import LetterTemplateDetailView, LetterTemplateListView

urlpatterns = [
    path("letter-templates/", LetterTemplateListView.as_view(), name="letter-template-list"),
    path(
        "letter-templates/<str:letter_type>/",
        LetterTemplateDetailView.as_view(),
        name="letter-template-detail",
    ),
]
