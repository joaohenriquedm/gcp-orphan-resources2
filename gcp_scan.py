# gcp_scan.py
import datetime as dt
import pandas as pd

from google.cloud import compute_v1
from google.cloud import monitoring_v3
from googleapiclient.discovery import build


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def days_ago(n: int) -> dt.datetime:
    return utc_now() - dt.timedelta(days=n)


def parse_ts(ts: str) -> dt.datetime:
    # Ex: "2024-01-01T12:34:56.789-07:00" ou "2024-01-01T12:34:56Z"
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def age_days(ts: str) -> int:
    if not ts:
        return -1
    return int((utc_now() - parse_ts(ts)).total_seconds() // 86400)


# =========================
# Compute - Orphans
# =========================

def get_unused_static_ips(project_id: str) -> pd.DataFrame:
    """
    Static external IPs reserved but unused (no users).
    """
    client = compute_v1.AddressesClient()
    req = compute_v1.AggregatedListAddressesRequest(project=project_id)

    rows = []
    for region, scoped in client.aggregated_list(request=req):
        if not scoped.addresses:
            continue

        for addr in scoped.addresses:
            # External only
            if getattr(addr, "address_type", None) != "EXTERNAL":
                continue

            status = getattr(addr, "status", None)
            users = list(getattr(addr, "users", []) or [])

            # Reserved and unused
            if status == "RESERVED" and len(users) == 0:
                rows.append({
                    "Project": project_id,
                    "Name": addr.name,
                    "IP": addr.address,
                    "Region": (region or "").replace("regions/", ""),
                    "Status": status,
                })

    return pd.DataFrame(rows)


def get_unattached_disks(project_id: str) -> pd.DataFrame:
    """
    Persistent disks not attached to any instance.
    """
    client = compute_v1.DisksClient()
    req = compute_v1.AggregatedListDisksRequest(project=project_id)

    rows = []
    for zone, scoped in client.aggregated_list(request=req):
        if not scoped.disks:
            continue

        for d in scoped.disks:
            users = list(getattr(d, "users", []) or [])
            if len(users) == 0:
                ts = getattr(d, "creation_timestamp", None)
                rows.append({
                    "Project": project_id,
                    "Name": d.name,
                    "Zone": (zone or "").replace("zones/", ""),
                    "Size_GB": int(d.size_gb) if d.size_gb is not None else None,
                    "Type": (d.type.split("/")[-1] if d.type else "unknown"),
                    "Age_Days": age_days(ts) if ts else None,
                })

    return pd.DataFrame(rows)


def get_snapshots(project_id: str) -> pd.DataFrame:
    """
    Snapshot inventory. 'Orphan snapshot' depends on your business rule,
    so we provide age + sourceDisk (when available).
    """
    client = compute_v1.SnapshotsClient()
    req = compute_v1.ListSnapshotsRequest(project=project_id)

    rows = []
    for s in client.list(request=req):
        ts = getattr(s, "creation_timestamp", None)
        source_disk = getattr(s, "source_disk", None)
        storage_bytes = getattr(s, "storage_bytes", None)

        rows.append({
            "Project": project_id,
            "Name": s.name,
            "Size_GB": int(storage_bytes // (1024**3)) if storage_bytes else 0,
            "Status": s.status,
            "Age_Days": age_days(ts) if ts else None,
            "Source_Disk": (source_disk.split("/")[-1] if source_disk else None),
        })

    return pd.DataFrame(rows)


# =========================
# Monitoring - CPU low usage
# =========================

def query_avg_metric(
    project_id: str,
    metric_type: str,
    resource_type: str,
    lookback_days: int,
    threshold: float,
) -> pd.DataFrame:
    """
    Queries a metric and returns resources whose average value over the lookback window is < threshold.
    For CPU utilization metrics, values are usually 0..1 (ex: 0.12 = 12%).
    """
    client = monitoring_v3.MetricServiceClient()

    interval = monitoring_v3.TimeInterval(
        end_time=utc_now(),
        start_time=days_ago(lookback_days),
    )

    aggregation = monitoring_v3.Aggregation(
        alignment_period=dt.timedelta(seconds=3600),
        per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    )

    request = monitoring_v3.ListTimeSeriesRequest(
        name=f"projects/{project_id}",
        filter=f'metric.type="{metric_type}" AND resource.type="{resource_type}"',
        interval=interval,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        aggregation=aggregation,
    )

    rows = []
    for ts in client.list_time_series(request=request):
        labels = dict(ts.resource.labels)

        rid = (
            labels.get("instance_id")
            or labels.get("instance_name")
            or labels.get("database_id")
            or labels.get("database")
            or labels.get("resource_name")
            or "unknown"
        )

        loc = labels.get("zone") or labels.get("region") or labels.get("location") or "unknown"

        values = []
        for p in ts.points:
            v = p.value
            if v.double_value is not None:
                values.append(float(v.double_value))
            elif v.int64_value is not None:
                values.append(float(v.int64_value))

        if not values:
            continue

        avg = sum(values) / len(values)
        if avg < threshold:
            rows.append({
                "Project": project_id,
                "Resource_ID": str(rid),
                "Location": str(loc),
                "Avg": round(avg, 4),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Avg"], ascending=True)
    else:
        df = pd.DataFrame(columns=["Project", "Resource_ID", "Location", "Avg"])
    return df


# =========================
# Cloud SQL inventory
# =========================

def get_cloudsql_instances(project_id: str) -> pd.DataFrame:
    """
    List Cloud SQL instances via SQL Admin API.
    """
    service = build("sqladmin", "v1", cache_discovery=False)
    resp = service.instances().list(project=project_id).execute()

    rows = []
    for i in resp.get("items", []) or []:
        rows.append({
            "Project": project_id,
            "Name": i.get("name"),
            "Region": i.get("region"),
            "Tier": i.get("settings", {}).get("tier"),
            "State": i.get("state"),
            "DB_Version": i.get("databaseVersion"),
        })

    return pd.DataFrame(rows)


def run_all(project_id: str, lookback_days: int, vm_cpu_th: float, sql_cpu_th: float) -> dict[str, pd.DataFrame]:
    """
    Returns a dict: {sheet_name: DataFrame}
    """
    dfs: dict[str, pd.DataFrame] = {}

    dfs["Unused_IPs"] = get_unused_static_ips(project_id)
    dfs["Unattached_Disks"] = get_unattached_disks(project_id)
    dfs["Snapshots"] = get_snapshots(project_id)

    dfs["Low_CPU_VMs"] = query_avg_metric(
        project_id=project_id,
        metric_type="compute.googleapis.com/instance/cpu/utilization",
        resource_type="gce_instance",
        lookback_days=lookback_days,
        threshold=vm_cpu_th,
    )

    dfs["Low_CPU_CloudSQL"] = query_avg_metric(
        project_id=project_id,
        metric_type="cloudsql.googleapis.com/database/cpu/utilization",
        resource_type="cloudsql_database",
        lookback_days=lookback_days,
        threshold=sql_cpu_th,
    )

    dfs["CloudSQL_Inventory"] = get_cloudsql_instances(project_id)

    return dfs
