from prometheus_client import Counter

hamamooz_backup_jobs_total = Counter(
    "hamamooz_backup_jobs_total",
    "Backup jobs by terminal outcome",
    ["resource", "operation", "outcome", "backup_outcome"],
)