"""Group intelligence enters each explicit tenant separately, never a bypass.

The anchor lodge remains the private history/usage owner. Group membership,
permissions, per-property plans and eligibility form a fresh ACL snapshot at
creation, every inference boundary, and saved-answer/retry replay.
"""

import hashlib, json
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from ..db import set_rls_context
from ..models import Lodge, LodgeGroup, Membership, Role, Subscription
from ..security import (
    require_permission,
    ensure_feature,
    membership_for,
    access_context,
    ensure_subscription_write_allowed,
    has_permission,
    entitlement_enabled,
)
from .context import guard, fingerprint

MAX_LODGES = 20


def _ids(db, user, group_id):
    return list(
        db.scalars(
            select(Lodge.id)
            .join(Membership, Membership.lodge_id == Lodge.id)
            .join(Role, Role.id == Membership.role_id)
            .where(
                Lodge.group_id == group_id,
                Membership.user_id == user.id,
                Membership.is_active.is_(True),
                Role.key == "group_admin",
            )
            .order_by(Lodge.id)
            .limit(MAX_LODGES + 1)
        )
    )


def resolve(db, user, anchor, request, expected_group=None):
    try:
        ctx = guard(db, user, anchor, request)
        if ctx.role_key != "group_admin":
            raise HTTPException(403, "Group Owner access is required")
        require_permission("ai.group.view")(
            lodge_id=str(anchor), request=request, user=ctx.user, db=db
        )
        ensure_feature(db, str(anchor), "advanced_ai")
        # AI conversations consume resources: every participating property must
        # have active write access, even though the returned CRM data is read-only.
        ensure_subscription_write_allowed(db, str(anchor))
        lodge = db.get(Lodge, anchor)
        group = db.get(LodgeGroup, lodge.group_id) if lodge.group_id else None
        if (
            not group
            or not group.is_active
            or group.admin_user_id != user.id
            or (expected_group and group.id != expected_group)
        ):
            raise HTTPException(403, "You do not have access to this AI group")
        gid, name = group.id, group.name
        ids = _ids(db, user, gid)
        if anchor not in ids:
            raise HTTPException(403, "Explicit lodge membership is required")
        if len(ids) > MAX_LODGES:
            raise HTTPException(
                413,
                "Group AI supports up to 20 assigned lodges. Use individual lodge AI for larger groups",
            )
        states = []
        eligible = []
        for lid in ids:
            # Collect membership-specific ACL data within this property's RLS.
            set_rls_context(db, str(lid), False, str(user.id))
            member = membership_for(db, user, str(lid))
            if not member:
                raise HTTPException(
                    409, "Group access changed. Start a new conversation"
                )
            pctx = access_context(db, user, str(lid))
            signature = fingerprint(db, pctx, lid)
            permitted = True
            try:
                pctx = guard(db, user, lid, request, write=True)
                if pctx.role_key != "group_admin":
                    raise HTTPException(403, "Group Owner access required")
                require_permission("ai.group.view")(
                    lodge_id=str(lid), request=request, user=pctx.user, db=db
                )
                ensure_feature(db, str(lid), "advanced_ai")
                if pctx.staff and pctx.staff.employment_status != "active":
                    raise HTTPException(403, "Staff access is inactive")
            except HTTPException as error:
                if error.status_code not in {401, 403}:
                    raise
                permitted = False
            states.append([str(lid), signature, permitted])
            if permitted:
                prop = db.get(Lodge, lid)
                eligible.append(
                    {
                        "lodge_id": str(lid),
                        "lodge_name": prop.brand_name or prop.name,
                        "timezone": prop.timezone,
                    }
                )
        # A mutation while walking the tenants must not produce a mixed snapshot.
        ctx = guard(db, user, anchor, request)
        current = db.get(LodgeGroup, gid)
        if (
            not current
            or not current.is_active
            or current.admin_user_id != user.id
            or db.get(Lodge, anchor).group_id != gid
            or _ids(db, user, gid) != ids
        ):
            raise HTTPException(409, "Group access changed. Start a new conversation")
        signature = hashlib.sha256(
            json.dumps([str(gid), str(user.id), states], sort_keys=True).encode()
        ).hexdigest()
        return {
            "group_id": str(gid),
            "group_name": name,
            "lodges": eligible,
            "excluded_count": len(ids) - len(eligible),
            "fingerprint": signature,
        }
    finally:
        set_rls_context(db, str(anchor), False, str(user.id))


def conversation_fingerprint(
    db, ctx, anchor, request, scope_type="lodge", group_id=None
):
    if scope_type == "lodge":
        return fingerprint(db, ctx, anchor)
    return resolve(db, ctx.user, anchor, request, group_id)["fingerprint"]


def summarise(items):
    """Only sum/count additive facts; never average percentages or invent scores."""
    metrics = {}
    for item in items:
        for key, value in item["metrics"].items():
            if type(value) not in (int, float):
                continue
            entry = metrics.setdefault(
                key,
                {
                    "total": 0,
                    "maximum": None,
                    "highest_lodge_ids": [],
                    "contributor_lodge_ids": [],
                },
            )
            entry["total"] += value
            entry["contributor_lodge_ids"].append(item["lodge_id"])
            if entry["maximum"] is None or value > entry["maximum"]:
                entry["maximum"] = value
                entry["highest_lodge_ids"] = [item["lodge_id"]]
            elif value == entry["maximum"]:
                entry["highest_lodge_ids"].append(item["lodge_id"])
    return metrics


def period(args):
    end = (
        date.fromisoformat(args.end_date)
        if args.end_date
        else datetime.now(timezone.utc).date()
    )
    if not 1900 <= end.year <= 9998:
        raise HTTPException(422, "Choose a valid report period")
    start = (
        date.fromisoformat(args.start_date)
        if args.start_date
        else end - timedelta(days=29)
    )
    if end < start or (end - start).days > 365:
        raise HTTPException(422, "Choose a report period of at most 366 days")
    return start, end


def execute(name, args, db, ctx, anchor, request):
    from . import tools
    from .. import main
    from ..services.metrics import housekeeping_counts

    state = resolve(db, ctx.user, anchor, request)
    expected = state["fingerprint"]
    items = []
    start, end = period(args) if name == "get_group_report_metrics" else (None, None)
    try:
        for prop in state["lodges"]:
            lid = UUID(prop["lodge_id"])
            pctx = guard(db, ctx.user, lid, request, write=True)
            metrics = {}
            metadata = (
                {
                    "period": {
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "timestamp_timezone": "UTC",
                    }
                }
                if start
                else {}
            )
            report_allowed = name == "get_group_overview"
            if name == "get_group_overview":
                tool = tools.REGISTRY["get_dashboard_summary"]
                if tools.allowed(db, pctx, tool, lid):
                    raw = tools.execute(
                        "get_dashboard_summary", {}, db, pctx, lid, request
                    )
                    metrics.update(raw["metrics"])
                    metadata["current_date"] = raw["scope"]["current_date"]
            else:
                tool = tools.REGISTRY["get_report_metrics"]
                report_allowed = tools.allowed(db, pctx, tool, lid)
                if report_allowed:
                    require_permission("reports.view")(
                        lodge_id=str(lid), request=request, user=pctx.user, db=db
                    )
                    ensure_feature(db, str(lid), "reports")
                    raw = main.reports_summary(
                        lodge_id=str(lid), start=start, end=end, user=pctx.user, db=db
                    )
                    # Match the live report tool's per-section grants, omit all costs,
                    # names, notes, averages, percentages and protected coordinates.
                    sections = {
                        "tasks": ("tasks.view", "tasks", ("created", "completed")),
                        "maintenance": (
                            "maintenance.view",
                            "maintenance",
                            ("created", "completed", "critical"),
                        ),
                        "guest_requests": (
                            "requests.view",
                            "guest_requests",
                            ("created", "resolved"),
                        ),
                        "stays": (
                            "stays.view",
                            "stays",
                            ("overlapping_period", "completed"),
                        ),
                        "fleet": ("fuel.view", "fuel", ("fuel_records",)),
                    }
                    for section, (permission, feature, keys) in sections.items():
                        if (
                            has_permission(db, pctx.membership, permission)
                            and entitlement_enabled(db, str(lid), feature)
                            and raw.get(section)
                        ):
                            metrics.update(
                                {f"{section}_{key}": raw[section][key] for key in keys}
                            )
                    metadata["period"] = {
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "timestamp_timezone": "UTC",
                    }
            hk = tools.REGISTRY["get_housekeeping_status"]
            if report_allowed and tools.allowed(db, pctx, hk, lid):
                require_permission("housekeeping.view")(
                    lodge_id=str(lid), request=request, user=pctx.user, db=db
                )
                ensure_feature(db, str(lid), "housekeeping")
                metrics.update(housekeeping_counts(db, lid, start, end))
            items.append(
                {
                    **prop,
                    **metadata,
                    "metrics": metrics,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        final = resolve(db, ctx.user, anchor, request)
        if final["fingerprint"] != expected:
            raise HTTPException(409, "Group access changed. Start a new conversation")
        comparisons = summarise(items)
        return {
            "scope": {
                "type": "group",
                "group_id": state["group_id"],
                "group_name": state["group_name"],
            },
            "items": items,
            "returned_count": len(items),
            "comparisons": comparisons,
            "partial": state["excluded_count"] > 0
            or any(
                len(m["contributor_lodge_ids"]) < len(items)
                for m in comparisons.values()
            ),
            "excluded_count": state["excluded_count"],
            "coverage": "Only explicitly assigned, AI-eligible lodges in this group. Missing metrics are unavailable, never zero. Each metric lists its own contributors. Counts are not workload-normalised performance or priority scores. Vehicle unavailability counts are current state, not downtime durations. Overview days use each lodge time zone. Reports describe records created in the UTC period, with current completion status, not completions during that period. Overlapping stays are not additive unique guests.",
        }
    finally:
        set_rls_context(db, str(anchor), False, str(ctx.user.id))
