from django.urls import path
from .views import AppListCreateView, AppDetailView

urlpatterns = [
    path("app", AppListCreateView.as_view(), name="app-list-create"),
    path("app/<int:pk>", AppDetailView.as_view(), name="app-detail"),
]
