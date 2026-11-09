"""Private report enrolment and reads. No public provider/identity parameters."""

from datetime import datetime, timezone
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from ..db import get_db
from ..models import AIReportSchedule, AIReportRun, AIMessage, Lodge, User
from ..security import require_permission, require_csrf, entitlement_enabled
from .context import guard
from . import reports
from .groups import resolve as resolve_group

router = APIRouter()
BASE = "/api/v1/lodges/{lodge_id}/ai/reports"


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["daily", "weekly"]
    scope: Literal["lodge", "group"] = "lodge"
    hour: int = Field(default=6, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    enabled: bool = True


@router.get(BASE)
def report_index(
    lodge_id: UUID,
    request: Request,
    scope: Literal["lodge", "group"] = "lodge",
    user: User = Depends(require_permission("ai.reports.manage")),
    db=Depends(get_db),
):
    ctx = guard(db, user, lodge_id, request)
    kinds = reports.available(db, ctx, lodge_id)
    if not kinds:
        raise HTTPException(403, "AI reports are not enabled for your account")
    if scope == "group":
        resolve_group(db, user, lodge_id, request)
    schedules = db.scalars(
        select(AIReportSchedule)
        .where(
            AIReportSchedule.scope_type == scope,
            AIReportSchedule.kind.in_(kinds),
            AIReportSchedule.user_id == user.id,
            AIReportSchedule.lodge_id == lodge_id,
        )
        .order_by(AIReportSchedule.kind)
    ).all()
    runs = db.execute(
        select(AIReportRun, AIReportSchedule)
        .join(AIReportSchedule, AIReportRun.schedule_id == AIReportSchedule.id)
        .where(AIReportSchedule.scope_type == scope, AIReportSchedule.kind.in_(kinds))
        .order_by(AIReportRun.created_at.desc())
        .limit(30)
    ).all()
    return {
        "kinds": kinds,
        "timezone": db.get(Lodge, lodge_id).timezone,
        "schedules": [reports.schedule_payload(s) for s in schedules],
        "runs": [
            {
                "id": str(r.id),
                "schedule_id": str(s.id),
                "kind": s.kind,
                "status": r.status,
                "scheduled_for": r.scheduled_for.isoformat(),
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "attempts": r.attempts,
                "error_code": r.error_code,
            }
            for r, s in runs
        ],
    }


@router.post(BASE + "/schedules", dependencies=[Depends(require_csrf)])
def save_schedule(
    lodge_id: UUID,
    body: ScheduleIn,
    request: Request,
    user: User = Depends(require_permission("ai.reports.manage", write=True)),
    db=Depends(get_db),
):
    ctx = guard(db, user, lodge_id, request, write=True)
    reports.authorize(db, ctx, lodge_id, body.kind)
    group = (
        resolve_group(db, user, lodge_id, request) if body.scope == "group" else None
    )
    request.state.report_kind = body.kind
    fp = reports.signature(
        db,
        ctx,
        lodge_id,
        request,
        body.scope,
        UUID(group["group_id"]) if group else None,
    )
    zone = db.get(Lodge, lodge_id).timezone
    next_run = reports.clock_next(
        body.kind,
        body.hour,
        body.minute,
        body.weekday,
        zone,
        datetime.now(timezone.utc),
    )
    row = db.scalar(
        select(AIReportSchedule)
        .where(
            AIReportSchedule.lodge_id == lodge_id,
            AIReportSchedule.user_id == user.id,
            AIReportSchedule.kind == body.kind,
            AIReportSchedule.scope_type == body.scope,
        )
        .with_for_update()
    )
    if not row:
        row = AIReportSchedule(
            lodge_id=lodge_id, user_id=user.id, kind=body.kind, scope_type=body.scope
        )
        db.add(row)
    if row.id:
        for pending in db.scalars(
            select(AIReportRun).where(
                AIReportRun.schedule_id == row.id,
                AIReportRun.status.in_(["queued", "running"]),
            )
        ).all():
            pending.status = "cancelled"
            pending.lease_token = None
            pending.lease_expires_at = None
            pending.error_code = "schedule_updated"
    row.group_id = UUID(group["group_id"]) if group else None
    row.hour = body.hour
    row.minute = body.minute
    row.weekday = body.weekday
    row.enabled = body.enabled
    row.timezone = zone
    row.next_run_at = next_run
    row.access_fingerprint = fp
    db.flush()
    from .. import main

    main.audit(
        db,
        request,
        lodge_id,
        user.id,
        "ai.report.schedule_updated",
        "ai_report_schedule",
        str(row.id),
    )
    result = reports.schedule_payload(row)
    db.commit()
    return result


@router.post(
    BASE + "/schedules/{schedule_id}/run", dependencies=[Depends(require_csrf)]
)
def run_now(
    lodge_id: UUID,
    schedule_id: UUID,
    request: Request,
    user: User = Depends(require_permission("ai.reports.manage", write=True)),
    db=Depends(get_db),
):
    ctx = guard(db, user, lodge_id, request, write=True)
    schedule = reports.get_schedule(db, lodge_id, user.id, schedule_id)
    reports.authorize(db, ctx, lodge_id, schedule.kind)
    if not schedule.enabled:
        raise HTTPException(409, "Enable the schedule before generating a report")
    request.state.report_kind = schedule.kind
    fp = reports.signature(
        db, ctx, lodge_id, request, schedule.scope_type, schedule.group_id
    )
    if schedule.access_fingerprint != fp:
        raise HTTPException(
            409, "Your access changed. Review and save the schedule again"
        )
    # Serialise repeated manual runs under the schedule lock.
    db.execute(
        select(AIReportSchedule)
        .where(AIReportSchedule.id == schedule.id)
        .with_for_update()
    )
    ctx = guard(db, user, lodge_id, request, write=True)
    db.refresh(schedule)
    reports.authorize(db, ctx, lodge_id, schedule.kind)
    if not schedule.enabled:
        raise HTTPException(409, "Enable the schedule before generating a report")
    request.state.report_kind = schedule.kind
    if (
        reports.signature(
            db, ctx, lodge_id, request, schedule.scope_type, schedule.group_id
        )
        != schedule.access_fingerprint
    ):
        raise HTTPException(
            409, "Your access changed. Review and save the schedule again"
        )
    row = reports.queue_now(db, schedule)
    result = {"id": str(row.id), "status": row.status}
    from .. import main

    main.audit(
        db, request, lodge_id, user.id, "ai.report.queued", "ai_report", str(row.id)
    )
    db.commit()
    # Beat drains the durable queue even if the broker was unavailable at enrolment.
    return result


@router.get(BASE + "/{run_id}")
def read_report(
    lodge_id: UUID,
    run_id: UUID,
    request: Request,
    user: User = Depends(require_permission("ai.reports.manage")),
    db=Depends(get_db),
):
    ctx = guard(db, user, lodge_id, request)
    row = db.scalar(
        select(AIReportRun).where(
            AIReportRun.id == run_id,
            AIReportRun.lodge_id == lodge_id,
            AIReportRun.user_id == user.id,
        )
    )
    if not row:
        raise HTTPException(404, "Report not found")
    schedule = reports.get_schedule(db, lodge_id, user.id, row.schedule_id)
    reports.authorize(db, ctx, lodge_id, schedule.kind)
    request.state.report_kind = schedule.kind
    if (
        reports.signature(
            db, ctx, lodge_id, request, schedule.scope_type, schedule.group_id
        )
        != row.access_fingerprint
    ):
        raise HTTPException(
            409, "Your access changed. This saved report is no longer available"
        )
    if row.status != "complete":
        raise HTTPException(409, "This report is not ready yet")
    answer = db.scalar(
        select(AIMessage)
        .where(
            AIMessage.conversation_id == row.conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.created_at.desc())
        .limit(1)
    )
    if not answer:
        raise HTTPException(404, "Report not found")
    from .routes import message_payload, verify_sources

    verify_sources(answer.sources, db, ctx, lodge_id, request)
    return {
        "id": str(row.id),
        "kind": schedule.kind,
        "scope": schedule.scope_type,
        "period": row.period,
        "generated_at": row.generated_at.isoformat(),
        "insights": row.insights,
        "insights_enabled": entitlement_enabled(db, str(lodge_id), "ai_insights"),
        "message": message_payload(answer),
    }
