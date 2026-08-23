from datetime import timedelta, timezone, datetime
from pathlib import Path
import base64
from django.db import transaction
from celery import shared_task
from kubernetes.stream import stream
from clusters.k8s_client import get_core_v1_api
from .models import Backup


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    soft_time_limit=3600,
    time_limit=3660,
)
def perform_backup(self, backup_id):
    backup = Backup.objects.get(id=backup_id)

    backup.status = "running"
    backup.save(update_fields=["status"])

    try:
        app = backup.app
        cluster = app.namespace.cluster

        core_api = get_core_v1_api(cluster)

        # Verify that the pod belongs to the application.
        pods = core_api.list_namespaced_pod(
            app.namespace.name,
            label_selector=f"app={app.name}",
            _request_timeout=5,
        )

        pod_names = {pod.metadata.name for pod in pods.items}

        if backup.pod_name not in pod_names:
            raise ValueError("Requested pod does not belong to this App")

        # Destination on the Celery worker.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup_dir = Path("/backups") / str(app.id) / today
        backup_dir.mkdir(parents=True, exist_ok=True)

        output_path = backup_dir / f"bkp_{backup.id}.tar.gz"

        # Create the tar.gz inside the pod and encode it as base64.
        # base64 makes it safe to transfer through the Kubernetes exec
        # text stream without corrupting binary tar.gz data.
        command = [
            "sh",
            "-c",
            f"tar -czf - {backup.source_path} | base64 -w 0",
        ]

        resp = stream(
            core_api.connect_get_namespaced_pod_exec,
            backup.pod_name,
            app.namespace.name,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        stdout_data = []
        stderr_data = []

        while resp.is_open():
            resp.update(timeout=1)

            if resp.peek_stdout():
                stdout_data.append(resp.read_stdout())

            if resp.peek_stderr():
                stderr_data.append(resp.read_stderr())

        resp.close()

        encoded_archive = "".join(stdout_data)
        stderr_output = "".join(stderr_data)

        if not encoded_archive:
            raise RuntimeError(
                f"Backup command returned no data. tar stderr: {stderr_output}"
            )

        archive_data = base64.b64decode(encoded_archive)

        with open(output_path, "wb") as f:
            f.write(archive_data)

        # Verify that the generated file is actually a gzip archive.
        if archive_data[:2] != b"\x1f\x8b":
            raise RuntimeError("Generated backup is not a valid gzip archive")

        backup.output_path = str(output_path)
        backup.status = "completed"
        backup.completed_at = datetime.now(timezone.utc)
        backup.error = "No error"

        backup.save(
            update_fields=[
                "output_path",
                "status",
                "completed_at",
                "error"
            ]
        )

    except Exception as exc:
        backup.status = "failed"
        backup.error = str(exc)
        backup.save(update_fields=["status", "error"])
        raise


    @shared_task
    def fail_stale_pending_backups():
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        stale_backups = Backup.objects.filter(
            status="pending",
            created_at__lt=cutoff,
        )

        count = 0

        for backup in stale_backups.iterator():
            with transaction.atomic():
                backup = Backup.objects.select_for_update().get(pk=backup.pk)

                # It may have been processed while this task was running.
                if backup.status != "pending":
                    continue

                backup.status = "failed"
                backup.error = (
                    "Backup remained pending for more than 24 hours. "
                    "The Celery worker or queue may have been unavailable."
                )
                backup.save(update_fields=["status", "error"])

                count += 1

        return count