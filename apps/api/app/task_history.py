"""Task context and immutable lifecycle reads; existing mutations stay authoritative."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from .db import get_db
from .models import (
    Task,
    TaskHistory,
    GuestRequest,
    StaffProfile,
    Department,
    Vehicle,
    MaintenanceTicket,
    User,
)
from .security import require_permission, ensure_feature, entitlement_enabled

router = APIRouter()


def may_read(db, ctx, lodge_id, permission, feature):
    from .main import _may

    return _may(db, ctx, permission) and entitlement_enabled(db, str(lodge_id), feature)


def maintenance_visible(ctx, ticket):
    from .main import _ensure_department_scope

    _ensure_department_scope(ctx, ticket.department_id, "maintenance ticket")
    if ctx.role_key in {"housekeeping", "ranger", "driver", "general_staff"}:
        if ticket.created_by_user_id != ctx.user.id and (
            not ctx.staff or ticket.assigned_staff_id != ctx.staff.id
        ):
            raise HTTPException(
                403,
                "You can only link maintenance tickets assigned to you or reported by you",
            )


def validate_links(db, ctx, lodge_id, vehicle_id, maintenance_ticket_id, unit_id):
    from .main import ensure_fk

    if vehicle_id:
        if not may_read(db, ctx, lodge_id, "vehicles.view", "fleet"):
            raise HTTPException(403, "Vehicle access is required to link this task")
        ensure_fk(db, Vehicle, vehicle_id, lodge_id, "Vehicle")
    if maintenance_ticket_id:
        if not may_read(db, ctx, lodge_id, "maintenance.view", "maintenance"):
            raise HTTPException(403, "Maintenance access is required to link this task")
        ticket = ensure_fk(
            db, MaintenanceTicket, maintenance_ticket_id, lodge_id, "Maintenance ticket"
        )
        maintenance_visible(ctx, ticket)
        if (
            vehicle_id
            and ticket.vehicle_id
            and str(vehicle_id) != str(ticket.vehicle_id)
        ):
            raise HTTPException(
                409, "The task and maintenance ticket must refer to the same vehicle"
            )
        if unit_id and ticket.unit_id and str(unit_id) != str(ticket.unit_id):
            raise HTTPException(
                409, "The task and maintenance ticket must refer to the same room"
            )


def lock_task(db, lodge_id, record_id, changes=None):
    from .main import tenant_get

    task = tenant_get(db, Task, record_id, lodge_id, "Task")
    # Shared order with confirmed AI actions: references and linked requests, then
    # the task at its table position. Refresh after locking before authorisation.
    refs = [(Task, task.id)]
    refs += [
        (GuestRequest, rid)
        for rid in db.scalars(
            select(GuestRequest.id).where(
                GuestRequest.lodge_id == lodge_id, GuestRequest.task_id == task.id
            )
        )
    ]
    if changes:
        models = {
            "assigned_staff_id": StaffProfile,
            "department_id": Department,
            "vehicle_id": Vehicle,
            "maintenance_ticket_id": MaintenanceTicket,
        }
        refs += [
            (model, getattr(changes, key))
            for key, model in models.items()
            if getattr(changes, key, None)
        ]
    for model, rid in sorted(
        refs, key=lambda item: (item[0].__tablename__, str(item[1]))
    ):
        db.scalar(
            select(model)
            .where(model.id == rid, model.lodge_id == lodge_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    db.refresh(task)
    return task


def task_details(db, ctx, task):
    lodge_id = task.lodge_id
    vehicle = None
    ticket = None
    if task.vehicle_id and may_read(db, ctx, lodge_id, "vehicles.view", "fleet"):
        vehicle = db.get(Vehicle, task.vehicle_id)
    if task.maintenance_ticket_id and may_read(
        db, ctx, lodge_id, "maintenance.view", "maintenance"
    ):
        candidate = db.get(MaintenanceTicket, task.maintenance_ticket_id)
        if candidate:
            try:
                maintenance_visible(ctx, candidate)
                ticket = candidate
            except HTTPException:
                pass
    end = task.completed_at or datetime.now(timezone.utc)
    elapsed = (
        max(0, int((end - task.created_at).total_seconds()))
        if task.completed_at
        else None
    )
    overdue = (
        max(0, int((end - task.due_at).total_seconds()))
        if task.due_at and task.status != "cancelled"
        else 0
    )
    from .main import _may

    return {
        "can_transition": bool(
            _may(db, ctx, "tasks.manage")
            or (
                _may(db, ctx, "tasks.own.manage")
                and ctx.staff
                and task.assigned_staff_id == ctx.staff.id
            )
        ),
        "created_at": task.created_at.isoformat(),
        "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
        "accepted_at": task.accepted_at.isoformat() if task.accepted_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "completion_seconds": elapsed,
        "overdue_seconds": overdue,
        "vehicle_id": str(vehicle.id) if vehicle else None,
        "vehicle_name": (vehicle.name or vehicle.registration) if vehicle else None,
        "maintenance_ticket_id": str(ticket.id) if ticket else None,
        "maintenance_title": ticket.title if ticket else None,
    }


def safe_snapshot(db, ctx, lodge_id, value, readable, ticket_cache):
    if value is None:
        return None
    result = deepcopy(value)
    if not readable["vehicles"]:
        result.pop("vehicle_id", None)
        result.pop("vehicle_name", None)
    ticket_id = result.get("maintenance_ticket_id")
    if not readable["maintenance"]:
        result.pop("maintenance_ticket_id", None)
        result.pop("maintenance_title", None)
    elif ticket_id:
        if ticket_id not in ticket_cache:
            ticket = db.get(MaintenanceTicket, UUID(ticket_id))
            try:
                if not ticket:
                    raise HTTPException(403)
                maintenance_visible(ctx, ticket)
                ticket_cache[ticket_id] = True
            except HTTPException:
                ticket_cache[ticket_id] = False
        if not ticket_cache[ticket_id]:
            result.pop("maintenance_ticket_id", None)
            result.pop("maintenance_title", None)
    return result


@router.get("/api/v1/lodges/{lodge_id}/tasks/{record_id}/history")
def history(
    lodge_id: UUID,
    record_id: UUID,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("tasks.view")),
    db=Depends(get_db),
):
    from .main import tenant_get, _ctx, _assert_task_visible

    ensure_feature(db, str(lodge_id), "tasks")
    ctx = _ctx(db, user, str(lodge_id))
    task = tenant_get(db, Task, record_id, lodge_id, "Task")
    _assert_task_visible(db, ctx, task)
    rows = db.scalars(
        select(TaskHistory)
        .where(TaskHistory.lodge_id == lodge_id, TaskHistory.task_id == task.id)
        .order_by(TaskHistory.sequence)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    items = []
    readable = {
        "vehicles": may_read(db, ctx, lodge_id, "vehicles.view", "fleet"),
        "maintenance": may_read(db, ctx, lodge_id, "maintenance.view", "maintenance"),
    }
    ticket_cache = {}
    for row in rows[:limit]:
        before = safe_snapshot(db, ctx, lodge_id, row.before, readable, ticket_cache)
        after = safe_snapshot(db, ctx, lodge_id, row.after, readable, ticket_cache)
        hidden = {k for k in ("vehicle_id", "maintenance_ticket_id") if k not in after}
        items.append(
            {
                "id": str(row.id),
                "kind": row.kind,
                "actor": row.actor_name,
                "occurred_at": row.occurred_at.isoformat(),
                "changed_fields": [f for f in row.changed_fields if f not in hidden],
                "before": before,
                "after": after,
            }
        )
    return {
        "items": items,
        "has_more": len(rows) > limit,
        "timing": task_details(db, ctx, task),
        "history_started_at": (
            rows[0].occurred_at.isoformat() if rows and offset == 0 else None
        ),
    }
