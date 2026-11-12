"""Offline replay is an idempotent adapter over the existing authorized workflows."""

import hashlib
import json
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from .db import get_db
from .models import OfflineReceipt, Task, TaskChecklistItem, HousekeepingJob, Transfer
from .security import (
    require_lodge_access,
    require_permission,
    require_csrf,
    ensure_feature,
    ensure_subscription_write_allowed,
)

router = APIRouter()


class OfflineAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    kind: Literal[
        "task.status", "task.checklist", "housekeeping.status", "transfer.status"
    ]
    record_id: UUID
    item_id: UUID | None = None
    expected: str | bool
    value: str | bool

    @model_validator(mode="after")
    def validate_operation(self):
        if self.kind == "task.checklist":
            if (
                self.item_id is None
                or type(self.expected) is not bool
                or type(self.value) is not bool
            ):
                raise ValueError(
                    "Checklist changes need an item and two boolean states"
                )
        elif (
            self.item_id is not None
            or not isinstance(self.expected, str)
            or not isinstance(self.value, str)
            or not (1 <= len(self.expected) <= 40 and 1 <= len(self.value) <= 40)
        ):
            raise ValueError("Status changes need a starting and target status")
        if self.kind != "task.checklist":
            from .schemas import TaskUpdate, HousekeepingUpdate, TransferUpdate

            schema = {
                "task.status": TaskUpdate,
                "housekeeping.status": HousekeepingUpdate,
                "transfer.status": TransferUpdate,
            }[self.kind]
            try:
                schema(status=self.value)
            except ValueError:
                raise ValueError("Choose a valid target status for this queued change")
        return self


@router.post(
    "/api/v1/lodges/{lodge_id}/offline-actions", dependencies=[Depends(require_csrf)]
)
def replay_action(
    lodge_id: str,
    body: OfflineAction,
    request: Request,
    user=Depends(require_lodge_access),
    db=Depends(get_db),
):
    # Import lazily: handlers remain the single source of workflow rules/auditing.
    from . import main
    from .schemas import (
        TaskUpdate,
        TaskChecklistUpdate,
        HousekeepingUpdate,
        TransferUpdate,
    )

    ensure_subscription_write_allowed(db, lodge_id)
    ensure_feature(db, lodge_id, "offline_mobile")
    feature, permission, model = {
        "task.status": ("tasks", "tasks.view", Task),
        "task.checklist": ("tasks", "tasks.view", Task),
        "housekeeping.status": ("housekeeping", "housekeeping.view", HousekeepingJob),
        "transfer.status": ("transfers", "transfers.view", Transfer),
    }[body.kind]
    require_permission(permission, write=True)(
        lodge_id=lodge_id, request=request, user=user, db=db
    )
    ensure_feature(db, lodge_id, feature)
    ctx = main._ctx(db, user, lodge_id)
    record = main.tenant_get(db, model, body.record_id, lodge_id, "Record")
    # Check record/write scope before disclosing conflict or receipt information.
    if model is Task:
        main._assert_task_visible(db, ctx, record)
        allowed = main._may(db, ctx, "tasks.manage") or (
            main._may(db, ctx, "tasks.own.manage")
            and ctx.staff
            and record.assigned_staff_id == ctx.staff.id
        )
    elif model is HousekeepingJob:
        allowed = (
            main._may(db, ctx, "housekeeping.manage")
            or (
                main._may(db, ctx, "housekeeping.own.manage")
                and ctx.staff
                and record.assigned_staff_id == ctx.staff.id
            )
            or (
                ctx.staff
                and record.inspector_staff_id == ctx.staff.id
                and body.value == "completed"
            )
        )
    else:
        main._ensure_department_scope(ctx, record.department_id, "transfer")
        allowed = main._may(db, ctx, "transfers.manage") or (
            main._may(db, ctx, "transfers.own.manage")
            and ctx.staff
            and record.driver_staff_id == ctx.staff.id
        )
    if not allowed:
        raise HTTPException(
            403, "You no longer have permission to apply this queued change"
        )
    digest = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"offline:{lodge_id}:{user.id}:{body.id}"},
    )
    receipt = db.get(OfflineReceipt, (body.id, UUID(lodge_id), user.id))
    if receipt:
        if receipt.request_hash != digest:
            raise HTTPException(
                409, "This queued change ID was already used for a different action"
            )
        return {"id": str(body.id), "status": "synced", "duplicate": True}
    # Lock before checking the expected starting state. Existing handlers still
    # perform their own scope, proof, inspection and transition checks.
    db.refresh(record, with_for_update=True)
    if body.kind == "task.checklist":
        item = main.tenant_get(
            db, TaskChecklistItem, body.item_id, lodge_id, "Checklist item"
        )
        if item.task_id != record.id:
            raise HTTPException(404, "Checklist item not found")
        db.refresh(item, with_for_update=True)
        current = bool(item.completed_at)
    else:
        current = record.status
    if current != body.expected:
        raise HTTPException(
            409,
            "This record changed while you were offline. Review its current state before retrying or discard this queued change.",
        )
    # The handler's commit includes this receipt and its mutation atomically.
    # A failed handler rolls both back; a lost acknowledgement can safely retry.
    db.add(
        OfflineReceipt(
            id=body.id, lodge_id=UUID(lodge_id), user_id=user.id, request_hash=digest
        )
    )
    if body.kind == "task.status":
        main.update_task(
            lodge_id,
            str(body.record_id),
            TaskUpdate(status=body.value),
            request,
            user,
            db,
        )
    elif body.kind == "task.checklist":
        main.update_task_checklist(
            lodge_id,
            str(body.record_id),
            str(body.item_id),
            TaskChecklistUpdate(completed=body.value),
            request,
            user,
            db,
        )
    elif body.kind == "housekeeping.status":
        main.update_housekeeping_job(
            lodge_id,
            str(body.record_id),
            HousekeepingUpdate(status=body.value),
            request,
            user,
            db,
        )
    else:
        main.update_transfer(
            lodge_id,
            str(body.record_id),
            TransferUpdate(status=body.value),
            request,
            user,
            db,
        )
    return {"id": str(body.id), "status": "synced", "duplicate": False}


from .schemas import WildlifeSightingCreate


@router.post(
    "/api/v1/lodges/{lodge_id}/offline-sightings", dependencies=[Depends(require_csrf)]
)
def replay_sighting(
    lodge_id: str,
    body: WildlifeSightingCreate,
    request: Request,
    user=Depends(require_permission("wildlife.manage", write=True)),
    db=Depends(get_db),
):
    from .main import create_wildlife

    ensure_feature(db, lodge_id, "offline_mobile")
    # Existing per-lodge client_ref idempotency is also used for online sightings.
    return create_wildlife(lodge_id, body, request, user, db)
