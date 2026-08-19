import json

from .redis_client import redis_client


def run_worker():
    print("Worker started...")

    while True:
        _, task_data = redis_client.blpop("task_queue")

        task = json.loads(task_data)

        if task["type"] == "print":
            print(f"Executing task: {task['message']}")