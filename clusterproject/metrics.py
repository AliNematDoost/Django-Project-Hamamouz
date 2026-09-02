from prometheus_client import Counter, Histogram

hamamooz_backup_jobs_total = Counter(
    "hamamooz_backup_jobs_total",
    "Backup jobs by terminal outcome",
    ["resource", "operation", "outcome", "backup_outcome"],
)

hamamooz_kubernetes_operations_total = Counter(
    "hamamooz_kubernetes_operations_total",
    "Number of Kubernetes API operations by resource, operation, and outcome",
    ["resource", "operation", "outcome"],
)

hamamooz_kubernetes_operation_duration_seconds = Histogram(
    "hamamooz_kubernetes_operation_duration_seconds",
    "Duration of Kubernetes operations",
    ["resource", "operation"],
)

hamamooz_backup_duration_seconds = Histogram(
    "hamamooz_backup_duration_seconds",
    "Duration of backup work",
)