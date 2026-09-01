from django.urls import path
from .views import NamespaceListCreateView, NamespaceDeleteView

urlpatterns = [
    path("namespace", NamespaceListCreateView.as_view(), name="namespace-list-create"),
    path("namespace/<int:pk>", NamespaceDeleteView.as_view(), name="namespace-delete"),
]
