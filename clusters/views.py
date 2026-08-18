from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Cluster
from .serializers import ClusterSerializer, ClusterTokenSerializer


class ClusterView(APIView):
    def get(self, request):
        clusters = Cluster.objects.all()
        serializer = ClusterSerializer(clusters, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ClusterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        try:
            cluster = Cluster.objects.get(pk=pk)
        except Cluster.DoesNotExist:
            return Response(
                {"detail": "Cluster not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClusterTokenSerializer(
            cluster,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                ClusterSerializer(cluster).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
