# Project Report

## Testing the Program

Using postman I have tested all senarios on APIs designed for Cluster, Namespace and Application. screenshots of tests are provided in this google drive `https://drive.google.com/drive/folders/1sBlLaGUU1SMOwKey6YAY7P79XEvpsCFM?usp=sharing`

For `application` I have used these fields ( a sample request body is provided )
```json
{
    "namespace_id": 2, 
    "name": "my-app", 
    "image": "nginx:latest", 
    "replicas": 2, 
    "cpu": "300m", 
    "memory": "64Mi"
}
```

The `App` model contains fields such as `namespace`, `name`, `image`, `replicas`, `cpu`, `memory`, and `created_at`. The `namespace` identifies where the App is deployed, while `name` and `image` define the application and its Docker image. `replicas`, `cpu`, and `memory` are used to specify the desired number of Pods and their resource requirements, with the same CPU and memory values used for both requests and limits. The `created_at` field records when the App was created. Additionally, the Deployment and all Pods it creates use the label `app: <app-name>`, which is also used by the Deployment selector to associate the Pods with the correct App.


## Problems which I solved

### PATCH request to update expired token of a cluster 
To handle cases where a Cluster token expires, a dedicated `PATCH` API was added to update only the token without creating a new Cluster or changing its existing information. This keeps the Cluster ID and its relationships with other resources unchanged while allowing the Kubernetes credential to be replaced. The API endpoint is `PATCH /cluster/<cluster_id>`. For example:

```json
{
    "token": "new-kubernetes-token"
}
```

The token is accepted in the request but is not returned in the response for security reasons.

### Consistency Between Database and Kubernetes

When deleting a Namespace, the operation involves two separate systems: the Django database and Kubernetes. Because they cannot be part of one atomic transaction, an inconsistency can occur if the Namespace is successfully deleted from Kubernetes but the backend crashes before removing its database record. To handle this, a later DELETE request checks Kubernetes again; if Kubernetes returns `404 Not Found`, it means the Namespace is already deleted there, so the backend safely removes the remaining database record as well. This allows the system to recover from this intermediate inconsistent state.

### Handling Concurrent DELETE Requests

If two DELETE requests for the same Namespace arrive at nearly the same time, `select_for_update()` places a row-level lock on the corresponding database record. The first transaction that acquires the lock performs the deletion and commits, while the other request waits until that transaction finishes. After the lock is released, the second request continues and finds that the database record has already been deleted, so it returns `404 Not Found`. This serializes concurrent database access to the same Namespace and prevents race conditions.


These two updates are applied to both namespace and application delete operations.

### Deleting scheduled backups after their app is deleted

Because ScheduleBackup.app is a foreign key, normally deleting the App will also delete its schedules because of `on_delete=models.CASCADE`. But checking it explicitly is still useful and I have done so in `process_scheduled_backups` using this code:
```
try:
    app = schedule.app
except App.DoesNotExist:
    continue
```

### Using app instead of pod name

At first I used to use an specific pod name to backup from, but after thinking deeper about concept of depeloyment I got that a Pod is ephemeral and after crashing deployment would remake another pod with a different pod name, so storing a specific Pod name in Backup/ScheduleBackup makes the schedule fragile.

So I decided to use app name for getting backup from one of it pods as mentioned in project doc. 

### Deactivate an scheduled backup 

We may need scheduled backup for a while and do not need it anymore, so I created a `PATCH` API to deactivate it. For that purpose created field `active` for each record of scheduled backup. 


## Instant Backup

### Request Execution Flow with Celery and Redis

**The backup API is implemented as an asynchronous task so that the HTTP request does not wait for the potentially time-consuming backup operation to finish.**

When a POST request is sent to the backup endpoint, the backend validates the requested application, pod, and source path, creates a Backup database record with pending status, and submits the backup task using perform_backup.delay(...). The API immediately returns 202 Accepted with the backup ID and current status.

The task is then handled by Celery. The Celery application is configured to use Redis as its broker, so the task message is placed into Redis. A running Celery worker consumes the task from Redis and executes perform_backup. The project also configures Redis as the Celery result backend.

While the worker is processing the task, the Backup record is updated from pending to running, and after successful completion it is changed to completed with the generated backup path. A separate GET request can then be used to check the current backup status.

---

### General Explanation of perform_backup

perform_backup is the Celery background task responsible for performing the complete backup operation.

It first retrieves the requested Backup record and marks it as running. It then obtains the Kubernetes connection associated with the application's cluster and verifies that the requested pod actually belongs to the application. After that, it creates a dated backup directory on the Celery worker and requests the selected pod to create a gzip-compressed tar archive of the specified source path.

Because the Kubernetes exec stream is not suitable for transporting raw binary data directly, the archive is Base64-encoded inside the pod. The worker receives the encoded data, decodes it back to binary, stores the resulting .tar.gz file under /backups, and verifies that the generated data is a valid gzip archive.

Finally, the task updates the database record with the backup path, completion status, and completion time. If an exception occurs, the backup is marked as failed and the exception is propagated so Celery's retry mechanism can handle it.



## Handling Backups Stuck in pending

A background Celery Beat task checks for backups that have remained in pending status for more than 24 hours. The check runs periodically and identifies backups whose created_at is older than the 24-hour threshold.

When such a backup is found, it is marked as failed and an error message is stored explaining that the task may have been affected by an unavailable worker or a stuck Celery queue.

## Scheduled Backups

Scheduled backups are separated from individual backup executions using two database models:

`ScheduleBackup` stores the recurring backup definition, including the application, pod, source path, backup due time, creation time, and active state.

`Backup` represents one actual backup execution and has its own ID, status, creation time, and is_scheduled flag.

The same POST /backup endpoint is used for both immediate and scheduled backups. When a schedule value is included, a ScheduleBackup record is created. **The API prevents duplicate active schedules with the same application, pod, source path, and Due time.**

Celery Beat runs the scheduled-backup task every minute. The task checks active ScheduleBackup records and uses their cron expressions to determine which schedules are due. For every matching schedule, it creates a new Backup record with is_scheduled=True and submits its ID to Celery.

The Celery worker then executes the normal perform_backup task, so scheduled and immediate backups use the same backup execution mechanism.

Each scheduled execution therefore receives a separate backup_id, appears in the application's backup list, and can be monitored through the normal backup status endpoint. A schedule can be deactivated by setting its active field to False; the record remains in the database but is no longer processed by the scheduler.

## Redis Cache for App Status

Redis is also used as a short-lived cache for the live status of each application.

When the App API requests application information, the backend first checks Redis using an App-specific cache key. If the status is available, the cached result is returned without querying Kubernetes.

On a cache miss, the backend queries Kubernetes for the application's Pods and calculates the current status, including whether the desired replicas are ready and the readiness of individual Pods. This live status is then stored in Redis with a TTL of 60 seconds.

After 60 seconds, the cache expires automatically, and the next request queries Kubernetes again and refreshes the cache.

Only live Kubernetes status is cached. The application's database data and Backup data are not stored in this cache.

Redis is separated into different logical databases: one for the Celery broker, one for Celery results, and one for application status caching.