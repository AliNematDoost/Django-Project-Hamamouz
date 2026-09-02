from datetime import timedelta, timezone, datetime
from pathlib import Path
import base64
from django.db import transaction
from celery import shared_task
from kubernetes.stream import stream
from clusters.k8s_client import get_core_v1_api
from .models import Backup, ScheduleBackup
from croniter import croniter
from applications.models import App
from clusterproject.metrics import hamamooz_backup_jobs_total
from clusterproject.metrics import hamamooz_kubernetes_operations_total
from clusterproject.metrics import hamamooz_kubernetes_operation_duration_seconds
from clusterproject.metrics import hamamooz_backup_duration_seconds
import time

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

    start = time.monotonic()

    backup.status = "running"
    backup.save(update_fields=["status"])

    try:
        app = backup.app
        cluster = app.namespace.cluster

        core_api = get_core_v1_api(cluster)

        try:
            start = time.monotonic()
            pods = core_api.list_namespaced_pod(
                app.namespace.name,
                label_selector=f"app={app.name}",
                _request_timeout=10,
            )
            duration = time.monotonic() - start

            hamamooz_kubernetes_operations_total.labels("app", "list", "success").inc()
            hamamooz_kubernetes_operation_duration_seconds.labels("app", "list").observe(duration)

        except Exception:
            hamamooz_kubernetes_operations_total.labels("app", "list", "error").inc()
            raise

        if not pods.items:
            raise ValueError(f"No pods found for App '{app.name}'")

        pod = pods.items[0]
        pod_name = pod.metadata.name

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup_dir = Path("/backups") / str(app.id) / today
        backup_dir.mkdir(parents=True, exist_ok=True)

        output_path = backup_dir / f"bkp_{backup.id}.tar.gz"

        command = [
            "sh",
            "-c",
            f"tar -czf - {backup.source_path} | base64 -w 0",
        ]

        try:
            start = time.monotonic()
            resp = stream(
                core_api.connect_get_namespaced_pod_exec,
                pod_name,
                app.namespace.name,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            duration = time.monotonic() - start

            hamamooz_kubernetes_operations_total.labels("app", "exec", "success").inc()
            hamamooz_kubernetes_operation_duration_seconds.labels("app", "exec").observe(duration)

        except Exception:
            hamamooz_kubernetes_operations_total.labels("app", "exec", "error").inc()
            raise

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

        if archive_data[:2] != b"\x1f\x8b":
            raise RuntimeError("Generated backup is not a valid gzip archive")

        duration = time.monotonic() - start
        hamamooz_backup_duration_seconds.observe(duration)
        
        backup.output_path = str(output_path)
        backup.status = "completed"
        backup.completed_at = datetime.now(timezone.utc)
        backup.error = "No error"
        backup.pod_name = pod_name

        backup.save(
            update_fields=["output_path", "status", "pod_name", "completed_at", "error"]
        )

        hamamooz_backup_jobs_total.labels("app", "create", "success", "completed").inc()
    except Exception as exc:
        backup.status = "failed"
        backup.error = str(exc)
        backup.save(update_fields=["status", "error"])

        hamamooz_backup_jobs_total.labels("app", "create", "error", "failed").inc()
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

            if backup.status != "pending":
                continue

            backup.status = "failed"
            backup.error = (
                "Backup remained pending for more than 24 hours. "
                "The Celery worker or queue may have been unavailable."
            )
            backup.save(update_fields=["status", "error"])
            hamamooz_backup_jobs_total.labels("app", "create", "error", "failed").inc()

            count += 1

    return count


@shared_task
def process_scheduled_backups():
    now = datetime.now(timezone.utc).replace(
        second=0,
        microsecond=0,
    )

    schedules = ScheduleBackup.objects.select_related(
        "app",
        "app__namespace",
        "app__namespace__cluster",
    ).filter(active=True)

    for schedule in schedules:
        try:
            app = schedule.app
        except App.DoesNotExist:
            continue

        if not croniter.match(
            schedule.schedule,
            now,
        ):
            continue

        backup = Backup.objects.create(
            app=schedule.app,
            source_path=schedule.source_path,
            status="pending",
            created_at=now,
            is_scheduled=True,
        )

        perform_backup.delay(str(backup.id))
