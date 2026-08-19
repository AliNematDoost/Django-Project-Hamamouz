import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clusterproject.settings")

app = Celery("clusterproject")

app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

app.autodiscover_tasks()