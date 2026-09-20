from django.urls import path

from done_board.views import DoneBoardView

urlpatterns = [
    path("done-board/", DoneBoardView.as_view(), name="done-board"),
]
