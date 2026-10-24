"""Deterministic operational aggregates under the caller's existing tenant RLS."""

from datetime import datetime, time, timedelta, timezone
from sqlalchemy import select, func
from ..models import HousekeepingJob


def housekeeping_counts(db, lodge_id, start=None, end=None):
    q = select(HousekeepingJob.status, func.count()).where(
        HousekeepingJob.lodge_id == lodge_id
    )
    if start and end:
        q = q.where(
            HousekeepingJob.created_at
            >= datetime.combine(start, time.min, tzinfo=timezone.utc),
            HousekeepingJob.created_at
            < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
        )
    counts = dict(db.execute(q.group_by(HousekeepingJob.status)).all())
    return {
        "housekeeping_created" if start else "housekeeping_jobs": sum(counts.values()),
        "housekeeping_open": sum(
            value
            for status, value in counts.items()
            if status not in {"completed", "cancelled"}
        ),
        "housekeeping_awaiting_inspection": counts.get("awaiting_inspection", 0),
        "housekeeping_completed": counts.get("completed", 0),
    }
