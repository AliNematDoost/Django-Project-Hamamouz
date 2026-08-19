from django.urls import path

from .views import TestTaskView


urlpatterns = [
    path("backup", TestTaskView.as_view(), name="test-task"),
]