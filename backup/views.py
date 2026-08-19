from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .tasks import print_test_task


class TestTaskView(APIView):

    def post(self, request):
        task = print_test_task.delay()

        return Response(
            {
                "message": "Task queued successfully",
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED
        )