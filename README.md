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

### No need to start app manually

Dockerfile for django app and docker-compose file are added to project, so that the whole project could be up using `docker compose up`. Using `start.sh` all three processes for django and celery worker and celery beat will be up in a single container.

## Instant Backup

### Request Execution Flow with Celery and Redis

A `POST /backup` request without `schedule` creates a `Backup` record with `pending` status and submits `perform_backup` to Celery. Celery places the task in Redis, and a Celery worker consumes and executes it. The API immediately returns `202 Accepted`.

The backup status changes from `pending` -> `running` -> `completed` or `failed`. The output path and execution details are stored in the database.

### `perform_backup`

`perform_backup` connects to the application's Kubernetes cluster, finds one current Pod belonging to the App, and creates a `.tar.gz` archive of the requested path. The archive is Base64-encoded during transfer, decoded by the worker, saved under `/backups`, and validated. The task uses controlled retries and time limits.

## Handling Backups Stuck in `pending`

A periodic Celery Beat task finds backups that have remained `pending` for more than 24 hours and marks them as `failed`.

The backup task also uses up to three controlled retries with backoff and execution time limits.

## Scheduled Backups

`ScheduleBackup` stores the recurring App backup definition: App, source path, cron expression, creation time, and active state. `Backup` represents each actual execution and has its own ID and `is_scheduled` flag.

The same `POST /backup` endpoint creates a schedule when `schedule` is provided. The cron expression is validated and duplicate active schedules are rejected.

Celery Beat checks active schedules every minute. When a schedule is due, it creates a new `Backup` record and submits it to Celery. The worker then executes the normal `perform_backup` task.

Each execution has its own `backup_id` and can be tracked through the normal backup endpoints. A schedule can be deactivated by setting `active=False`.

## Redis Cache for App Status

Redis caches the live Kubernetes status of each App for **60 seconds**.

On a cache hit, the API returns the cached status without querying Kubernetes. On a miss, it queries the App's Pods, calculates the current status, and stores it in Redis.

Only App status is cached; Backup and other application data remain in the database.

Redis uses separate logical databases for the Celery broker, Celery results, and App-status cache.
