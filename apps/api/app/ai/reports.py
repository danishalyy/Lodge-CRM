"""Actor-bound private report policy, schedule calculations and deterministic findings."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from ..config import settings
from ..db import set_rls_context
from ..models import AIReportRun, AIReportSchedule, Lodge, User, LodgeGroup
from ..security import (
    access_context,
    has_permission,
    ensure_feature,
    ensure_subscription_write_allowed,
)
from .context import guard, fingerprint
from .groups import conversation_fingerprint

FEATURES = {"daily": "ai_daily_summary", "weekly": "ai_weekly_report"}


def clock_next(kind, hour, minute, weekday, zone, after):
    """First local occurrence after `after`; skip nonexistent DST times, first fold only."""
    tz = ZoneInfo(zone)
    local = after.astimezone(tz)
    for offset in range(15):
        day = local.date() + timedelta(days=offset)
        if kind == "weekly" and day.weekday() != weekday:
            continue
        candidate = datetime.combine(day, time(hour, minute), tzinfo=tz)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(tz).replace(tzinfo=None) != candidate.replace(tzinfo=None):
            continue
        if utc > after:
            return utc
    raise HTTPException(422, "Choose a valid report time")


def actor_scope(db, lodge_id, actor_id):
    db.expire_all()
    set_rls_context(db, str(lodge_id), False, str(actor_id))
    user = db.get(User, actor_id)
    lodge = db.get(Lodge, lodge_id)
    if not lodge or lodge.status != "active":
        raise HTTPException(403, "Report lodge access changed")
    if not user or not user.is_active or user.is_super_admin:
        raise HTTPException(403, "Report access changed")
    ctx = access_context(db, user, str(lodge_id))
    if ctx.staff and ctx.staff.employment_status != "active":
        raise HTTPException(403, "Report access changed")
    ensure_subscription_write_allowed(db, str(lodge_id))
    if not has_permission(db, ctx.membership, "ai.use"):
        raise HTTPException(403, "Report access changed")
    ensure_feature(db, str(lodge_id), "ai")
    return ctx


def available(db, ctx, lodge_id):
    lodge = db.get(Lodge, lodge_id)
    if not lodge or lodge.status != "active":
        return []
    if (
        not settings.ai_enabled
        or not settings.ai_summaries_enabled
        or ctx.user.is_super_admin
    ):
        return []
    if not all(
        has_permission(db, ctx.membership, key)
        for key in ["ai.use", "ai.reports.manage", "reports.view"]
    ):
        return []
    from ..security import entitlement_enabled

    if not entitlement_enabled(db, str(lodge_id), "reports"):
        return []
    from .tools import allowed, REGISTRY

    sources = {
        "daily": any(
            allowed(db, ctx, REGISTRY[name], lodge_id)
            for name in ("get_dashboard_summary", "get_tasks")
        ),
        "weekly": allowed(db, ctx, REGISTRY["get_report_metrics"], lodge_id),
    }
    return [
        kind
        for kind, feature in FEATURES.items()
        if sources[kind] and entitlement_enabled(db, str(lodge_id), feature)
    ]


def authorize(db, ctx, lodge_id, kind):
    if kind not in available(db, ctx, lodge_id):
        raise HTTPException(403, "This AI report is not enabled for your account")
    ensure_subscription_write_allowed(db, str(lodge_id))
    return ctx


def signature(db, ctx, lodge_id, request, scope, group_id=None):
    previous = getattr(request.state, "ai_report_feature", None)
    try:
        if scope == "group" and getattr(request.state, "report_kind", None) in FEATURES:
            request.state.ai_report_feature = FEATURES[request.state.report_kind]
        return conversation_fingerprint(db, ctx, lodge_id, request, scope, group_id)
    finally:
        request.state.ai_report_feature = previous


def report_guard(db, user, lodge_id, request):
    """A server-only lease principal, rechecked at every normal tool boundary."""
    if not user or user.id != request.actor_id:
        raise HTTPException(403, "Report owner changed")
    anchor = request.anchor_id
    ctx = actor_scope(db, anchor, request.actor_id)
    run = db.get(AIReportRun, request.run_id)
    from .principals import ReportReadRequest

    reading = isinstance(request, ReportReadRequest)
    if not run or run.user_id != user.id or run.lodge_id != anchor:
        raise HTTPException(404, "Report not found")
    if reading:
        if run.status != "complete":
            raise HTTPException(409, "Report is not ready")
    elif (
        run.status != "running"
        or run.lease_token != request.lease_token
        or not run.lease_expires_at
        or run.lease_expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(409, "Report lease expired")
    schedule = db.get(AIReportSchedule, run.schedule_id)
    if not schedule or (not reading and not schedule.enabled):
        raise HTTPException(409, "Report schedule was paused")
    authorize(db, ctx, anchor, schedule.kind)
    request.state.report_kind = schedule.kind
    request.state.ai_report_feature = (
        FEATURES[schedule.kind] if schedule.scope_type == "group" else None
    )
    lodge = db.get(Lodge, anchor)
    if schedule.timezone != lodge.timezone:
        raise HTTPException(409, "Report timezone changed; review the schedule")
    if str(lodge_id) != str(anchor):
        if schedule.scope_type != "group":
            raise HTTPException(403, "Report lodge scope is fixed")
        group_id = schedule.group_id
        kind = schedule.kind
        ctx = actor_scope(db, lodge_id, request.actor_id)
        authorize(db, ctx, lodge_id, kind)
        prop = db.get(Lodge, lodge_id)
        group = db.get(LodgeGroup, group_id)
        if (
            ctx.role_key != "group_admin"
            or not prop
            or prop.group_id != group_id
            or not group
            or not group.is_active
            or group.admin_user_id != user.id
        ):
            raise HTTPException(403, "Report group access changed")
    return ctx


def get_schedule(db, lodge_id, user_id, schedule_id):
    row = db.scalar(
        select(AIReportSchedule).where(
            AIReportSchedule.id == schedule_id,
            AIReportSchedule.lodge_id == lodge_id,
            AIReportSchedule.user_id == user_id,
        )
    )
    if not row:
        raise HTTPException(404, "Report schedule not found")
    return row


def schedule_payload(row):
    return {
        "id": str(row.id),
        "kind": row.kind,
        "scope": row.scope_type,
        "hour": row.hour,
        "minute": row.minute,
        "weekday": row.weekday,
        "timezone": row.timezone,
        "enabled": row.enabled,
        "next_run_at": row.next_run_at.isoformat(),
    }


def queue_now(db, schedule):
    pending = db.scalar(
        select(AIReportRun)
        .where(
            AIReportRun.schedule_id == schedule.id,
            AIReportRun.status.in_(["queued", "running"]),
        )
        .order_by(AIReportRun.created_at)
        .limit(1)
    )
    if pending:
        return pending
    row = AIReportRun(
        lodge_id=schedule.lodge_id,
        user_id=schedule.user_id,
        schedule_id=schedule.id,
        slot_key="manual:" + uuid4().hex,
        scheduled_for=datetime.now(timezone.utc),
        access_fingerprint=schedule.access_fingerprint,
    )
    db.add(row)
    db.flush()
    return row


def findings(facts):
    """Bounded rule findings; no invented causes, risk scores or predicted outcomes."""
    metrics = next(
        (
            row["data"].get("metrics", {})
            for row in facts
            if row["tool"] == "get_dashboard_summary"
        ),
        {},
    )
    output = []
    for key in ["overdue_tasks", "maintenance_open", "vehicles_unavailable"]:
        value = metrics.get(key)
        if isinstance(value, (int, float)) and value > 0:
            output.append({"key": key, "count": value, "tool": "get_dashboard_summary"})
    if "overdue_tasks" not in metrics:
        rows = next(
            (
                row["data"].get("items", [])
                for row in facts
                if row["tool"] == "get_tasks"
            ),
            [],
        )
        if rows:
            output.append(
                {"key": "listed_overdue_tasks", "count": len(rows), "tool": "get_tasks"}
            )
    group = next((row for row in facts if row["tool"] == "get_group_overview"), None)
    if group:
        for key in ["overdue_tasks", "maintenance_open", "vehicles_unavailable"]:
            item = group["data"].get("comparisons", {}).get(key, {})
            if type(item.get("total")) in {int, float} and item["total"] > 0:
                output.append(
                    {
                        "key": key,
                        "count": item["total"],
                        "tool": "get_group_overview",
                        "contributor_lodge_ids": item["contributor_lodge_ids"],
                    }
                )
    return output


def notification_authorized(db, notification, user):
    from sqlalchemy import text
    from .principals import ReportReadRequest

    previous = db.execute(
        text(
            "SELECT current_setting('app.current_lodge_id',true),current_setting('app.is_super_admin',true),current_setting('app.current_user_id',true)"
        )
    ).one()
    try:
        request = ReportReadRequest(
            notification.lodge_id, user.id, UUID(str(notification.resource_id))
        )
        ctx = report_guard(db, user, notification.lodge_id, request)
        row = db.get(AIReportRun, UUID(str(notification.resource_id)))
        schedule = db.get(AIReportSchedule, row.schedule_id)
        return (
            signature(
                db,
                ctx,
                notification.lodge_id,
                request,
                schedule.scope_type,
                schedule.group_id,
            )
            == row.access_fingerprint
        )
    except Exception:
        return False
    finally:
        set_rls_context(
            db, previous[0] or None, previous[1] == "true", previous[2] or ""
        )
