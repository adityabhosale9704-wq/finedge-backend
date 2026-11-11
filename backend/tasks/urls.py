from django.urls import path

from tasks.views import (
    TaskDetailView,
    TaskDoneView,
    TaskListCreateView,
    TaskUndoView,
)

urlpatterns = [
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("<str:task_id>/", TaskDetailView.as_view(), name="task-detail"),
    path("<str:task_id>/done/", TaskDoneView.as_view(), name="task-done"),
    path("<str:task_id>/undo/", TaskUndoView.as_view(), name="task-undo"),
]
