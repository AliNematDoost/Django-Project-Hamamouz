from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException
from clusters.models import Cluster
from .models import Namespace
from .serializers import NamespaceSerializer
from .k8s_client import get_core_v1_api
from django.db import transaction
from clusterproject.metrics import hamamooz_kubernetes_operations_total

class NamespaceListCreateView(APIView):
    def get(self, request):
        cluster_id = request.query_params.get("cluster_id")
        if not cluster_id:
            return Response(
                {"error": "cluster_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        namespaces = Namespace.objects.filter(cluster_id=cluster_id)
        serializer = NamespaceSerializer(namespaces, many=True)
        return Response(serializer.data)

    def post(self, request):
        cluster_id = request.data.get("cluster_id")
        name = request.data.get("name")
        if not cluster_id or not name:
            return Response(
                {"error": "cluster_id and name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            return Response(
                {"error": "Cluster not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if Namespace.objects.filter(cluster=cluster, name=name).exists():
            return Response(
                {"error": "Namespace already recorded for this cluster"},
                status=status.HTTP_409_CONFLICT,
            )

        api = get_core_v1_api(cluster)
        body = k8s_client.V1Namespace(metadata=k8s_client.V1ObjectMeta(name=name))
        try:
            api.create_namespace(body)
            hamamooz_kubernetes_operations_total.labels(
                "namespace", "create", "success"
            ).inc()

        except ApiException as e:
            hamamooz_kubernetes_operations_total.labels(
                "namespace", "create", "error"
            ).inc()

            if e.status == 409:
                return Response(
                    {"error": "Namespace already exists in Kubernetes"},
                    status=status.HTTP_409_CONFLICT,
                )

            elif e.status in (401, 403):
                return Response(
                    {"error": "Not authorized to create namespace"}, status=e.status
                )

            else:
                return Response(
                    {"error": "Kubernetes error", "detail": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception as e:
            hamamooz_kubernetes_operations_total.labels(
                "namespace", "create", "error"
            ).inc()
            return Response(
                {"error": "Cannot reach Kubernetes cluster", "detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        namespace = Namespace.objects.create(cluster=cluster, name=name)
        serializer = NamespaceSerializer(namespace)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NamespaceDeleteView(APIView):
    def delete(self, request, pk):
        try:
            with transaction.atomic():

                # Lock this database row so another DELETE request
                # cannot modify/delete it at the same time.
                namespace = Namespace.objects.select_for_update().get(id=pk)

                cluster = namespace.cluster

                api = get_core_v1_api(cluster)

                try:
                    api.delete_namespace(namespace.name)
                    hamamooz_kubernetes_operations_total.labels(
                        "namespace", "delete", "success"
                    ).inc()

                except ApiException as e:
                    hamamooz_kubernetes_operations_total.labels(
                        "namespace", "delete", "error"
                    ).inc()

                    # Namespace is already gone from Kubernetes.
                    # We can safely remove the database record.
                    if e.status == 404:
                        namespace.delete()

                        return Response(status=status.HTTP_204_NO_CONTENT)

                    return Response(
                        {"error": "Kubernetes error", "detail": str(e)},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

                except Exception as e:
                    hamamooz_kubernetes_operations_total.labels(
                        "namespace", "delete", "error"
                    ).inc()
                    return Response(
                        {"error": "Cannot reach Kubernetes cluster", "detail": str(e)},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

                # Kubernetes deletion succeeded.
                namespace.delete()

                return Response(status=status.HTTP_204_NO_CONTENT)

        except Namespace.DoesNotExist:
            return Response(
                {"error": "Namespace not found"}, status=status.HTTP_404_NOT_FOUND
            )
