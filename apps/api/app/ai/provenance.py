"""Server-authored provenance shared by chat and scheduled reports."""

from datetime import datetime, timezone
from . import tools


def source_for(name, result, lodge_id):
    source = {
        "kind": tools.REGISTRY[name].source_kind,
        "label": tools.REGISTRY[name].label,
        "lodge_id": str(lodge_id),
        "partial": bool(result.get("partial")),
        "record_ids": [r["id"] for r in result.get("items", []) if r.get("id")],
        "tool": name,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    if source["kind"] == "memory":
        source["period"] = result["period"]
        source["references"] = [
            {
                key: row[key]
                for key in (
                    "id",
                    "resource_type",
                    "resource_id",
                    "recorded_at",
                )
            }
            for row in result.get("items", [])
        ]
    if source["kind"] == "document":
        source["references"] = [
            {
                key: row[key]
                for key in (
                    "id",
                    "document_id",
                    "title",
                    "locator",
                    "sha256",
                )
            }
            for row in result.get("items", [])
        ]
    if source["kind"] == "group":
        source["group_id"] = result["scope"]["group_id"]
        source["group_name"] = result["scope"]["group_name"]
        source["excluded_count"] = result["excluded_count"]
        source["references"] = [
            {
                **{
                    key: row[key]
                    for key in (
                        "lodge_id",
                        "lodge_name",
                        "timezone",
                        "period",
                        "current_date",
                        "retrieved_at",
                    )
                    if key in row
                },
                "metric_keys": list(row["metrics"]),
            }
            for row in result["items"]
        ]
        source["contributors"] = {
            key: value["contributor_lodge_ids"]
            for key, value in result["comparisons"].items()
        }
    return source
