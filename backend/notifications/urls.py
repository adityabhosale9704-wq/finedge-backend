from django.urls import path

from notifications.views import NotificationsView

urlpatterns = [
    path("notifications/", NotificationsView.as_view(), name="notifications"),
]
