import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .redis_client import redis_client


class TestTaskView(APIView):

    def post(self, request):
        task = {
            "type": "print",
            "message": "Hello from background worker!"
        }

        redis_client.rpush(
            "task_queue",
            json.dumps(task)
        )

        return Response(
            {
                "message": "Task queued successfully"
            },
            status=status.HTTP_202_ACCEPTED
        )