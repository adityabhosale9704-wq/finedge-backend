from django.urls import path

from employees.views import EmployeeDetailView, EmployeeListCreateView

urlpatterns = [
    path("", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("<str:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
]
