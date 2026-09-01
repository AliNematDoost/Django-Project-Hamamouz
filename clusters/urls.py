from django.urls import path
from .views import ClusterView

urlpatterns = [
    path("cluster", ClusterView.as_view(), name="cluster"),
    path("cluster/<int:pk>", ClusterView.as_view(), name="cluster-detail"),
]
