from prometheus_client import Counter

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
