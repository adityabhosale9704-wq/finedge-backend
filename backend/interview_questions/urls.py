from django.urls import path

from interview_questions.views import (
    InterviewQuestionDetailView,
    InterviewQuestionListCreateView,
)

urlpatterns = [
    path(
        "interview-questions/",
        InterviewQuestionListCreateView.as_view(),
        name="interview-question-list-create",
    ),
    path(
        "interview-questions/<str:pk>/",
        InterviewQuestionDetailView.as_view(),
        name="interview-question-detail",
    ),
]
