from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task
from kubernetes.client.rest import ApiException

from applications.models import App
from clusters.k8s_client import get_core_v1_api
from .models import Backup
from kubernetes.stream import stream


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def perform_backup(self, backup_id):
    backup = Backup.objects.get(id=backup_id)

    backup.status = "running"
    backup.save(update_fields=["status"])

    try:
        app = backup.app
        cluster = app.namespace.cluster

        core_api = get_core_v1_api(cluster)

        # Make sure the requested pod really belongs to this App.
        pods = core_api.list_namespaced_pod(
            app.namespace.name,
            label_selector=f"app={app.name}",
            _request_timeout=5,
        )

        pod_names = {pod.metadata.name for pod in pods.items}

        if backup.pod_name not in pod_names:
            raise ValueError("Requested pod does not belong to this App")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup_dir = Path("/backups") / str(app.id) / today
        backup_dir.mkdir(parents=True, exist_ok=True)

        output_path = backup_dir / f"bkp_{backup.id}.tar.gz"

        # Execute tar inside the selected pod.
        command = [
            "tar",
            "czf",
            str(output_path),
            backup.source_path,
        ]

        # NOTE:
        # This is the conceptual execution step.
        # The output path is inside the pod, not the worker.
        #
        # We still need to stream/copy the generated archive
        # from the pod to the worker filesystem.

        resp = stream(
            core_api.connect_get_namespaced_pod_exec,
            backup.pod_name,
            app.namespace.name,
            command=["tar", "czf", "-", backup.source_path],
            stderr=True, stdin=False, stdout=True, tty=False,
            _preload_content=False,
        )

        while resp.is_open():
            resp.update(timeout=1)
            if resp.peek_stderr():
                err = resp.read_stderr()

        resp.close()

        with open(output_path, "wb") as f:
            f.write(resp.read_all().encode('utf-8', errors='surrogateescape'))

        # `result` needs to be handled according to your Kubernetes
        # client execution/streaming method in your installed client.
        # The next step below will copy the archive to the worker.

        backup.output_path = str(output_path)
        backup.status = "completed"
        backup.completed_at = datetime.now(timezone.utc)
        backup.save(
            update_fields=[
                "output_path",
                "status",
                "completed_at",
            ]
        )

    except Exception as exc:
        backup.status = "failed"
        backup.error = str(exc)
        backup.save(update_fields=["status", "error"])
        raise