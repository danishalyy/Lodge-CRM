"""Permission-filtered projection of immutable CRM events, never chat memory.

Free-form event summaries/details are deliberately not inference input. Legacy
unit-level housekeeping creation events cannot identify the job/assignee, so
are excluded instead of guessing their visibility.
"""

from datetime import datetime, time, timedelta
from sqlalchemy import select, and_, or_
from fastapi import HTTPException
from ..models import OperationalEvent
from ..security import require_permission, ensure_feature

# Exact event/resource pairs fail closed for new, sensitive or ambiguous types.
FAMILIES = {
    "guest_request": (
        "get_guest_requests",
        {
            "guest_request.created": "Guest request created",
            "guest_request.status_changed": "Guest request status changed",
            "guest_request.task_created": "Task created from guest request",
        },
    ),
    "activity": (
        "get_activity_schedule",
        {
            "activity.created": "Activity created",
            "activity.updated": "Activity updated",
        },
    ),
    "transfer": (
        "get_transfer_schedule",
        {
            "transfer.created": "Transfer created",
            "transfer.updated": "Transfer updated",
        },
    ),
    "task": (
        "get_tasks",
        {
            "task.created": "Task created",
            "task.status_changed": "Task status changed",
            "task.recurrence_created": "Recurring task created",
        },
    ),
    "maintenance": (
        "get_maintenance_status",
        {
            "maintenance.created": "Maintenance ticket created",
            "maintenance.status_changed": "Maintenance status changed",
            "maintenance.recurrence_created": "Recurring maintenance scheduled",
        },
    ),
    "unit": (
        "get_room_status",
        {
            "unit.created": "Room created",
            "unit.status_changed": "Room status changed",
        },
    ),
    "vehicle": (
        "get_vehicle_status",
        {
            "vehicle.created": "Vehicle created",
            "vehicle.updated": "Vehicle updated",
        },
    ),
    "housekeeping": (
        "get_housekeeping_status",
        {
            "housekeeping.status_changed": "Housekeeping status changed",
        },
    ),
}
STATUSES = {
    "created",
    "open",
    "assigned",
    "accepted",
    "in_progress",
    "waiting",
    "completed",
    "cancelled",
    "awaiting_inspection",
    "available",
    "occupied",
    "cleaning",
    "ready",
    "maintenance",
    "out_of_service",
}


def read_history(args, db, ctx, lodge_id, request, zone, today):
    from .tools import REGISTRY, allowed, read_rows, Arguments

    end = (
        datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else today
    )
    if not 1900 <= end.year <= 9998:
        raise HTTPException(422, "Choose a valid history period")
    start = (
        datetime.strptime(args.start_date, "%Y-%m-%d").date()
        if args.start_date
        else end - timedelta(days=29)
    )
    if end < start or (end - start).days > 365:
        raise HTTPException(422, "Choose a history period of at most 366 days")
    conditions, records = [], {}
    scope_partial = False
    for resource, (name, events) in FAMILIES.items():
        if args.resource_type and resource != args.resource_type:
            continue
        tool = REGISTRY[name]
        if not allowed(db, ctx, tool, lodge_id):
            continue
        require_permission(tool.permission)(
            lodge_id=str(lodge_id), request=request, user=ctx.user, db=db
        )
        ensure_feature(db, str(lodge_id), tool.feature)
        # Bounded authoritative list, including department/assignment checks.
        rows = read_rows(tool, Arguments(), db, ctx, lodge_id, bound=250)
        scope_partial |= len(rows) >= 250
        ids = []
        for row in rows[:250]:
            safe = {key: row.get(key) for key in tool.fields}
            if args.resource_id and safe.get("id") != args.resource_id:
                continue
            if (
                args.search
                and args.search.casefold()
                not in " ".join(str(v or "") for v in safe.values()).casefold()
            ):
                continue
            rid = safe["id"]
            ids.append(rid)
            records[(resource, rid)] = {
                "current_record_label": safe.get("title")
                or safe.get("name")
                or safe.get("unit_name")
                or safe.get("request_type")
                or safe.get("transfer_type")
                or rid,
                "current_room_label": safe.get("unit_name"),
                "current_vehicle_label": safe.get("vehicle_name"),
            }
        if ids:
            conditions.append(
                and_(
                    OperationalEvent.resource_type == resource,
                    OperationalEvent.resource_id.in_(ids),
                    OperationalEvent.event_type.in_(events),
                )
            )
    rows = []
    if conditions:
        rows = db.scalars(
            select(OperationalEvent)
            .where(
                OperationalEvent.lodge_id == lodge_id,
                or_(*conditions),
                OperationalEvent.created_at
                >= datetime.combine(start, time.min, tzinfo=zone),
                OperationalEvent.created_at
                < datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone),
            )
            .order_by(OperationalEvent.created_at.desc(), OperationalEvent.id.desc())
            .limit(args.limit + 1)
        ).all()
    items = []
    for row in rows[: args.limit]:
        # A strict terminal enum is the only historical value extracted from text.
        # Never substitute the record's CURRENT status for a historical transition.
        status = row.summary.rsplit(" changed to ", 1)[-1]
        item = {
            "id": str(row.id),
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "event_type": row.event_type,
            "action": FAMILIES[row.resource_type][1][row.event_type],
            "recorded_at": row.created_at.isoformat(),
            **records[(row.resource_type, row.resource_id)],
        }
        if (
            row.event_type.endswith(".status_changed")
            and " changed to " in row.summary
            and status in STATUSES
        ):
            item["recorded_status"] = status
        items.append(item)
    return {
        "items": items,
        "returned_count": len(items),
        "partial": scope_partial or len(rows) > args.limit,
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "coverage": "Supported event types for currently visible records only. Deleted, inaccessible and unsupported records/events are excluded. At most 250 current records per permitted module are checked. Current labels may differ from historical labels. Logs do not establish causes or complete recurrence totals.",
    }


def verify_sources(sources, db, ctx, lodge_id, request):
    """Do not replay a saved historical answer after record reassignment/deletion.

    A permission fingerprint alone cannot detect an individual task moving to
    another department. Recheck the referenced records through the same readers.
    """
    from .tools import REGISTRY, allowed, read_rows, Arguments

    references = {}
    for source in sources:
        if source.get("kind") != "memory":
            continue
        if not allowed(db, ctx, REGISTRY["get_operational_history"], lodge_id):
            raise HTTPException(
                409, "Historical source access changed. Start a new conversation"
            )
        for ref in source.get("references", []):
            references.setdefault(ref["resource_type"], set()).add(ref["resource_id"])
    for resource, ids in references.items():
        if resource not in FAMILIES:
            raise HTTPException(
                409, "Historical source access changed. Start a new conversation"
            )
        tool = REGISTRY[FAMILIES[resource][0]]
        if not allowed(db, ctx, tool, lodge_id):
            raise HTTPException(
                409, "Historical source access changed. Start a new conversation"
            )
        require_permission(tool.permission)(
            lodge_id=str(lodge_id), request=request, user=ctx.user, db=db
        )
        ensure_feature(db, str(lodge_id), tool.feature)
        visible = {
            row["id"]
            for row in read_rows(tool, Arguments(), db, ctx, lodge_id, bound=250)
        }
        if not ids <= visible:
            raise HTTPException(
                409, "Historical source access changed. Start a new conversation"
            )
