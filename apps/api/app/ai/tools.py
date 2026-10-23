"""Explicit read-only adapters around authoritative CRM endpoints.

No generic database, shell, URL, identity or arbitrary scope tool exists.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from collections import Counter
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from typing import Literal
from ..models import Lodge
from ..security import (
    require_permission,
    ensure_feature,
    has_permission,
    entitlement_enabled,
)
from .context import guard
from .safety import redact


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=30, ge=1, le=50)
    status: (
        Literal[
            "open",
            "assigned",
            "accepted",
            "started",
            "in_progress",
            "waiting",
            "pending",
            "completed",
            "cancelled",
            "resolved",
            "available",
            "occupied",
            "cleaning",
            "awaiting_inspection",
            "ready",
            "maintenance",
            "out_of_service",
            "planned",
            "scheduled",
            "delayed",
            "in_house",
            "upcoming",
            "checked_out",
        ]
        | None
    ) = None
    search: str | None = Field(default=None, max_length=80)
    on_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    overdue_only: bool = False

    @field_validator("on_date")
    @classmethod
    def validate_day(cls, value):
        if value:
            date.fromisoformat(value)
        return value


@dataclass(frozen=True)
class Tool:
    permission: str
    feature: str
    handler: str
    fields: tuple
    label: str
    suggestion: str
    filters: tuple = ("limit", "status", "search")
    extra_permissions: tuple = ()


REGISTRY = {
    "get_dashboard_summary": Tool(
        "dashboard.view",
        "dashboard",
        "dashboard",
        (),
        "Operational overview",
        "What needs attention today?",
        (),
    ),
    "get_tasks": Tool(
        "tasks.view",
        "tasks",
        "tasks",
        ("id", "title", "status", "priority", "due_at", "unit_name"),
        "Tasks",
        "Which tasks are overdue?",
        ("limit", "status", "search", "overdue_only"),
    ),
    "get_room_status": Tool(
        "units.view",
        "units",
        "rooms",
        ("id", "name", "unit_type", "status"),
        "Rooms and readiness",
        "Which rooms are not ready?",
    ),
    "get_current_stays": Tool(
        "stays.view",
        "stays",
        "stays",
        (
            "id",
            "unit_name",
            "guest_name",
            "arrival_date",
            "departure_date",
            "party_size",
            "status",
        ),
        "Stays",
        "Which stays are currently in house?",
        ("limit", "status", "on_date"),
    ),
    "get_arrivals": Tool(
        "stays.view",
        "stays",
        "stays",
        (
            "id",
            "unit_name",
            "guest_name",
            "arrival_date",
            "departure_date",
            "party_size",
            "status",
        ),
        "Guest arrivals",
        "Which guests arrive today?",
        ("limit", "on_date"),
    ),
    "get_departures": Tool(
        "stays.view",
        "stays",
        "stays",
        (
            "id",
            "unit_name",
            "guest_name",
            "arrival_date",
            "departure_date",
            "party_size",
            "status",
        ),
        "Guest departures",
        "Which guests depart today?",
        ("limit", "on_date"),
    ),
    "get_guest_requests": Tool(
        "requests.view",
        "guest_requests",
        "requests_list",
        ("id", "request_type", "status", "priority", "created_at"),
        "Guest requests",
        "Which guest requests need attention?",
    ),
    "get_housekeeping_status": Tool(
        "housekeeping.view",
        "housekeeping",
        "list_housekeeping_jobs",
        ("id", "unit_name", "job_type", "status", "due_at"),
        "Housekeeping",
        "Which housekeeping jobs are outstanding?",
    ),
    "get_maintenance_status": Tool(
        "maintenance.view",
        "maintenance",
        "maintenance_list",
        (
            "id",
            "title",
            "category",
            "status",
            "priority",
            "unit_name",
            "vehicle_name",
            "scheduled_for",
        ),
        "Maintenance",
        "Which maintenance issues are open?",
    ),
    "get_vehicle_status": Tool(
        "vehicles.view",
        "fleet",
        "list_vehicles",
        (
            "id",
            "name",
            "registration",
            "status",
            "odometer_km",
            "fuel_level_percent",
            "service_due_in_km",
        ),
        "Vehicle readiness",
        "Which vehicles need attention?",
    ),
    "get_fuel_status": Tool(
        "fuel.view",
        "fuel",
        "list_fuel",
        ("id", "vehicle_name", "litres", "odometer_km", "recorded_at"),
        "Fuel logs",
        "What fuel records are available?",
        ("limit",),
    ),
    "get_activity_schedule": Tool(
        "activities.view",
        "activities",
        "list_activities",
        ("id", "title", "activity_type", "starts_at", "ends_at", "status"),
        "Activities",
        "What activities are scheduled today?",
        ("limit", "status", "on_date"),
    ),
    "get_transfer_schedule": Tool(
        "transfers.view",
        "transfers",
        "list_transfers",
        (
            "id",
            "transfer_type",
            "scheduled_at",
            "status",
            "delay_minutes",
            "passenger_count",
        ),
        "Transfers",
        "What transfers are scheduled today?",
        ("limit", "status", "on_date"),
    ),
    "get_notifications": Tool(
        "notifications.view",
        "notifications",
        "list_notifications",
        ("id", "type", "severity", "created_at", "read_at"),
        "Your notifications",
        "Which of my notifications need attention?",
        ("limit",),
    ),
    "get_report_metrics": Tool(
        "reports.view",
        "reports",
        "reports_summary",
        (),
        "Operational report metrics",
        "Give me the operational report metrics.",
        (),
    ),
}


def allowed(db, ctx, tool, lodge_id):
    return (
        (
            tool.handler not in {"reports_summary", "dashboard"}
            or ctx.role_key
            in {
                "lodge_admin",
                "group_admin",
                "department_manager",
                "front_office",
                "finance",
                "read_only",
            }
        )
        and not ctx.user.is_super_admin
        and all(
            has_permission(db, ctx.membership, p)
            for p in (tool.permission, *tool.extra_permissions)
        )
        and entitlement_enabled(db, str(lodge_id), tool.feature)
    )


def available(db, ctx, lodge_id):
    definitions = []
    for name, tool in REGISTRY.items():
        if not allowed(db, ctx, tool, lodge_id):
            continue
        properties = {
            key: value
            for key, value in Arguments.model_json_schema()["properties"].items()
            if key in tool.filters
        }
        if "status" in properties:
            properties["status"] = {"type": ["string", "null"], "maxLength": 32}
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.label
                    + ". Read-only authorised data; results may be a partial page. Never infer missing records or totals.",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return definitions


def permission(db, ctx, key):
    return has_permission(db, ctx.membership, key)


def clean(value):
    if isinstance(value, str):
        return redact(value[:512])
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def execute(name, arguments, db, ctx, lodge_id, request):
    # Re-authenticate independently for every invocation; never trust the orchestrator's earlier decision.
    ctx = guard(db, ctx.user, lodge_id, request)
    tool = REGISTRY.get(name)
    if not tool:
        raise HTTPException(422, "AI tool is not registered")
    if not isinstance(arguments, dict) or set(arguments) - set(tool.filters):
        raise HTTPException(422, "AI tool arguments are invalid")
    try:
        args = Arguments.model_validate(arguments)
    except ValidationError:
        raise HTTPException(422, "AI tool arguments are invalid") from None
    require_permission(tool.permission)(
        lodge_id=str(lodge_id), request=request, user=ctx.user, db=db
    )
    ensure_feature(db, str(lodge_id), tool.feature)
    if not allowed(db, ctx, tool, lodge_id):
        raise HTTPException(403, "This AI tool is not available to your account")
    from .. import main

    lodge = db.get(Lodge, lodge_id)
    try:
        zone = ZoneInfo(lodge.timezone)
    except Exception:
        zone = ZoneInfo("Africa/Johannesburg")
    today = datetime.now(zone).date()
    target = date.fromisoformat(args.on_date) if args.on_date else today
    output = {
        "scope": {
            "lodge_id": str(lodge_id),
            "lodge_name": lodge.name,
            "timezone": lodge.timezone,
            "current_date": today.isoformat(),
        },
        "source": tool.label,
    }
    handler = getattr(main, tool.handler)
    if name == "get_dashboard_summary":
        raw = handler(lodge_id=str(lodge_id), user=ctx.user, db=db)
        metric_access = {
            "guests_in_house": ("stays.view", "stays"),
            "arrivals_today": ("stays.view", "stays"),
            "departures_today": ("stays.view", "stays"),
            "open_tasks": ("tasks.view", "tasks"),
            "overdue_tasks": ("tasks.view", "tasks"),
            "maintenance_open": ("maintenance.view", "maintenance"),
            "activities_today": ("activities.view", "activities"),
            "transfers_today": ("transfers.view", "transfers"),
            "vehicles_unavailable": ("vehicles.view", "fleet"),
        }
        output["metrics"] = {
            {
                "guests_in_house": "in_house_stays",
                "arrivals_today": "stays_arriving_today",
                "departures_today": "stays_departing_today",
            }.get(key, key): value
            for key, value in raw["metrics"].items()
            if key in metric_access
            and permission(db, ctx, metric_access[key][0])
            and entitlement_enabled(db, str(lodge_id), metric_access[key][1])
        }
        output["scope"]["record_scope"] = raw.get("scope")
        return clean(output)
    if name == "get_report_metrics":
        # The legacy report handler is manager/department oriented. Do not widen it to assigned-work scopes.
        if ctx.role_key not in {
            "lodge_admin",
            "group_admin",
            "department_manager",
            "front_office",
            "finance",
            "read_only",
        }:
            raise HTTPException(
                403, "This report is unavailable for your operational scope"
            )
        raw = handler(
            lodge_id=str(lodge_id), start=None, end=None, user=ctx.user, db=db
        )
        access = {
            "tasks": ("tasks.view", "tasks"),
            "maintenance": ("maintenance.view", "maintenance"),
            "guest_requests": ("requests.view", "guest_requests"),
            "stays": ("stays.view", "stays"),
            "rooms": ("units.view", "units"),
            "fleet": ("fuel.view", "fuel"),
        }
        output["period"] = raw.get("period")
        output["metrics"] = {
            key: {
                k: v
                for k, v in raw[key].items()
                if not isinstance(v, (dict, list, str)) and "cost" not in k
            }
            for key, (p, f) in access.items()
            if raw.get(key)
            and permission(db, ctx, p)
            and entitlement_enabled(db, str(lodge_id), f)
        }
        return clean(output)
    kwargs = {"lodge_id": str(lodge_id), "user": ctx.user, "db": db}
    if tool.handler == "tasks":
        kwargs.update(status=args.status, assignee_id=None, limit=101, offset=0)
    elif tool.handler == "stays":
        kwargs.update(limit=101, offset=0)
    elif tool.handler in {
        "rooms",
        "requests_list",
        "maintenance_list",
        "list_housekeeping_jobs",
        "list_vehicles",
    }:
        kwargs["limit"] = 101
    elif tool.handler == "list_notifications":
        kwargs.update(unread_only=False, limit=101)
    rows = handler(**kwargs)
    partial = (
        len(rows) >= 101
        if tool.handler not in {"list_activities", "list_transfers", "list_fuel"}
        else len(rows) >= 500
    )
    selected = rows
    if args.status:
        selected = [r for r in selected if r.get("status") == args.status]
    if args.search:
        selected = [
            r
            for r in selected
            if args.search.casefold()
            in " ".join(str(r.get(k, "")) for k in tool.fields).casefold()
        ]
    if args.overdue_only:
        now = datetime.now(timezone.utc)
        selected = [
            r
            for r in selected
            if r.get("due_at")
            and datetime.fromisoformat(r["due_at"]) < now
            and r.get("status") not in {"completed", "cancelled"}
        ]
    if name in {"get_arrivals", "get_departures"}:
        key = "arrival_date" if name == "get_arrivals" else "departure_date"
        selected = [
            r
            for r in selected
            if r.get(key) == target.isoformat() and r.get("status") != "cancelled"
        ]
    elif name == "get_current_stays":
        selected = [r for r in selected if r.get("status") == "in_house"]
    elif name in {"get_activity_schedule", "get_transfer_schedule"}:
        key = "starts_at" if name == "get_activity_schedule" else "scheduled_at"
        selected = [
            r
            for r in selected
            if r.get(key)
            and datetime.fromisoformat(r[key]).astimezone(zone).date() == target
        ]
    output.update(
        items=[
            {key: r.get(key) for key in tool.fields} for r in selected[: args.limit]
        ],
        returned_count=min(len(selected), args.limit),
        partial=partial or len(selected) > args.limit,
        filters=arguments,
    )
    # Names, guest contacts, medical information, HR, finances, notes and precise wildlife positions are not in these DTOs.
    return clean(output)
