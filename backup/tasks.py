from celery import shared_task


@shared_task
def print_test_task():
    print("Hello from Celery worker!")