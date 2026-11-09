from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models import (
    AIReportRun,
    AIReportSchedule,
    AIConversation,
    AIMessage,
    AIUsage,
    Notification,
    User,
    LodgeEntitlementOverride,
    Membership,
    Subscription,
    Lodge,
)
from app.ai.providers.testing import TestProvider
from app.ai.providers.base import Completion, ProviderUnavailable
from app.ai.report_jobs import generate, dispatch
from test_ai_foundation import ai
from test_ai_groups import group_ai


@pytest.fixture
def scheduled(ai, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_summaries_enabled", True)
    with ai["owner"]() as db:
        for key in ["ai_daily_summary", "ai_weekly_report", "ai_insights"]:
            db.add(
                LodgeEntitlementOverride(
                    lodge_id=ai["lodge"].id,
                    feature_key=key,
                    enabled=True,
                    reason="Scheduled report test",
                )
            )
        db.commit()
    ai["reports"] = ai["base"] + "/reports"
    return ai


def schedule(a, kind="daily", scope="lodge"):
    result = a["client"].post(
        a["reports"] + "/schedules",
        json={"kind": kind, "scope": scope, "hour": 6, "minute": 15},
        headers=a["csrf"],
    )
    assert result.status_code == 200, result.text
    return result.json()


def queued(a, kind="daily", scope="lodge"):
    s = schedule(a, kind, scope)
    response = a["client"].post(
        a["reports"] + "/schedules/" + s["id"] + "/run", headers=a["csrf"]
    )
    assert response.status_code == 200, response.text
    return s, response.json()["id"]


def dispatch_all(a, enqueue=None):
    cursor = None
    total = 0
    for _ in range(100):
        result = dispatch(
            session_factory=a["application"], enqueue=enqueue, cursor=cursor
        )
        total += result["queued"]
        cursor = result.get("next_cursor")
        if not cursor:
            return {"queued": total}
    raise AssertionError("Dispatcher pagination did not terminate")


def run(a, rid, provider=None):
    return generate(
        a["lodge"].id,
        a["user"].id,
        rid,
        session_factory=a["application"],
        provider=provider
        or TestProvider(
            [
                Completion(
                    "Fixture report from checked operational facts.",
                    input_tokens=100,
                    output_tokens=10,
                )
            ]
        ),
    )


def test_daily_report_is_private_read_only_and_idempotent(scheduled):
    a = scheduled
    s, rid = queued(a)
    assert run(a, rid)["status"] == "complete"
    assert run(a, rid)["status"] == "skipped"
    result = a["client"].get(a["reports"] + "/" + rid)
    assert result.status_code == 200, result.text
    data = result.json()
    assert (
        data["message"]["content"].startswith("Fixture report")
        and len(data["message"]["sources"]) >= 8
    )
    assert data["period"]["timezone"] == s["timezone"] and data["period"]["snapshot_at"]
    assert a["client"].get(a["base"] + "/conversations").json() == []
    with a["owner"]() as db:
        r = db.get(AIReportRun, rid)
        assert r.status == "complete" and r.attempts == 1
        cid = str(r.conversation_id)
        assert db.get(AIConversation, cid).origin == "report"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIUsage)
                .where(AIUsage.conversation_id == r.conversation_id)
            )
            == 1
        )
        notifications = db.scalars(
            select(Notification).where(
                Notification.lodge_id == a["lodge"].id,
                Notification.notification_type == "ai.report.ready",
            )
        ).all()
        assert len(notifications) == 1 and "Fixture report" not in notifications[0].body
    assert (
        a["client"].get(a["base"] + f"/conversations/{cid}/messages").status_code == 404
    )
    assert (
        a["client"]
        .post(
            a["base"] + f"/conversations/{cid}/messages",
            json={"request_id": str(uuid4()), "content": "Change this report"},
            headers=a["csrf"],
        )
        .status_code
        == 404
    )


def test_schedule_requests_require_csrf_and_cannot_choose_other_identity(scheduled):
    a = scheduled
    assert (
        a["client"]
        .post(a["reports"] + "/schedules", json={"kind": "daily"})
        .status_code
        == 403
    )
    assert (
        a["client"]
        .post(
            a["reports"] + "/schedules",
            json={"kind": "daily", "user_id": str(uuid4())},
            headers=a["csrf"],
        )
        .status_code
        == 422
    )
    assert (
        a["client"]
        .post(
            a["reports"] + "/schedules",
            json={"kind": "daily", "hour": 24},
            headers=a["csrf"],
        )
        .status_code
        == 422
    )
    assert a["client"].get(a["reports"] + "/" + str(uuid4())).status_code == 404
    s = schedule(a)
    again = schedule(a)
    assert s["id"] == again["id"]
    assert datetime.fromisoformat(s["next_run_at"]) > datetime.now(timezone.utc)


def test_manual_queue_coalesces_repeated_clicks(scheduled):
    a = scheduled
    s, rid = queued(a)
    again = a["client"].post(
        a["reports"] + "/schedules/" + s["id"] + "/run", headers=a["csrf"]
    )
    assert again.status_code == 200 and again.json()["id"] == rid


def test_bounded_dispatch_recovers_due_and_does_not_duplicate_slots(scheduled):
    a = scheduled
    s = schedule(a)
    with a["owner"]() as db:
        row = db.get(AIReportSchedule, s["id"])
        row.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    enqueued = []
    first = dispatch_all(a, enqueue=lambda *args: enqueued.append(args))
    second = dispatch_all(a)
    assert first["queued"] >= 1 and second["queued"] >= 1
    assert len([args for args in enqueued if args[1] == str(a["user"].id)]) == 1
    with a["owner"]() as db:
        rows = db.scalars(
            select(AIReportRun).where(AIReportRun.schedule_id == s["id"])
        ).all()
        assert len(rows) == 1
        assert db.get(AIReportSchedule, s["id"]).next_run_at > datetime.now(
            timezone.utc
        )


@pytest.mark.parametrize(
    "change", ["membership", "subscription", "feature", "timezone", "lodge", "pause"]
)
def test_report_does_not_publish_when_access_changes_during_inference(
    scheduled, change
):
    a = scheduled
    s, rid = queued(a)

    class Changing(TestProvider):
        def complete(self, messages, tools):
            with a["owner"]() as db:
                if change == "membership":
                    db.scalar(
                        select(Membership).where(Membership.user_id == a["user"].id)
                    ).is_active = False
                elif change == "subscription":
                    db.get(Subscription, a["lodge"].id).suspended = True
                elif change == "feature":
                    db.get(
                        LodgeEntitlementOverride,
                        {"lodge_id": a["lodge"].id, "feature_key": "ai_daily_summary"},
                    ).enabled = False
                elif change == "lodge":
                    db.get(Lodge, a["lodge"].id).status = "inactive"
                elif change == "timezone":
                    db.get(Lodge, a["lodge"].id).timezone = "Europe/London"
                else:
                    db.get(AIReportSchedule, s["id"]).enabled = False
                db.commit()
            return Completion("PRIVATE OUTDATED REPORT")

    assert run(a, rid, Changing())["status"] == "unavailable"
    with a["owner"]() as db:
        r = db.get(AIReportRun, rid)
        assert r.status == "cancelled"
        assert not db.scalar(
            select(AIMessage.id).where(
                AIMessage.conversation_id == r.conversation_id,
                AIMessage.role == "assistant",
            )
        )
        assert not db.scalar(
            select(Notification.id).where(
                Notification.lodge_id == a["lodge"].id,
                Notification.notification_type == "ai.report.ready",
            )
        )


def test_provider_failure_is_durable_and_successful_retry_deduplicates_notification(
    scheduled,
):
    a = scheduled
    s, rid = queued(a)
    assert run(a, rid, TestProvider([ProviderUnavailable()]))["status"] == "unavailable"
    with a["owner"]() as db:
        row = db.get(AIReportRun, rid)
        assert row.status == "queued" and row.attempts == 1
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert run(a, rid)["status"] == "complete"
    with a["owner"]() as db:
        row = db.get(AIReportRun, rid)
        assert row.attempts == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.lodge_id == a["lodge"].id,
                    Notification.notification_type == "ai.report.ready",
                )
            )
            == 1
        )


def test_weekly_report_uses_completed_seven_utc_calendar_days(scheduled):
    a = scheduled
    s, rid = queued(a, "weekly")
    provider = TestProvider([Completion("Fixture weekly report")])
    assert run(a, rid, provider)["status"] == "complete"
    result = a["client"].get(a["reports"] + "/" + rid).json()
    period = result["period"]
    start = datetime.fromisoformat(period["start_date"]).date()
    end = datetime.fromisoformat(period["end_date"]).date()
    assert (end - start).days == 6 and end == datetime.now(
        timezone.utc
    ).date() - timedelta(days=1)
    assert provider.calls[0][1] == []
    assert "created_in_period_UTC" in str(provider.calls[0][0])


def test_group_report_uses_current_explicit_memberships_and_keeps_other_group_out(
    group_ai, scheduled
):
    a = scheduled
    s, rid = queued(a, scope="group")
    provider = TestProvider([Completion("Fixture group report")])
    result = run(a, rid, provider)
    assert result["status"] == "complete", result
    report = a["client"].get(a["reports"] + "/" + rid)
    assert report.status_code == 200, report.text
    source = report.json()["message"]["sources"][0]
    assert source["kind"] == "group" and len(source["references"]) == 1
    assert source["excluded_count"] == 1
    assert "UNASSIGNED PROPERTY" not in str(
        provider.calls
    ) and "OTHER GROUP PROPERTY" not in str(provider.calls)


def test_completed_report_and_email_are_hidden_after_permission_change(scheduled):
    from app.email_jobs import notification_still_authorized
    from app.db import set_rls_context

    a = scheduled
    s, rid = queued(a)
    assert run(a, rid)["status"] == "complete"
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        n = db.scalar(
            select(Notification).where(Notification.lodge_id == a["lodge"].id)
        )
        assert notification_still_authorized(
            db,
            n,
            db.get(User, a["user"].id),
        )
    with a["owner"]() as db:
        db.get(
            LodgeEntitlementOverride,
            {"lodge_id": a["lodge"].id, "feature_key": "ai_daily_summary"},
        ).enabled = False
        db.commit()
    assert a["client"].get(a["reports"] + "/" + rid).status_code == 403
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        n = db.scalar(
            select(Notification).where(Notification.lodge_id == a["lodge"].id)
        )
        assert not notification_still_authorized(
            db,
            n,
            db.get(User, a["user"].id),
        )


def test_background_principal_cannot_prepare_writes(scheduled):
    from app.ai.actions import authorize
    from app.ai.principals import ReportRequest
    from fastapi import HTTPException

    a = scheduled
    s, rid = queued(a)
    with a["application"]() as db:
        with pytest.raises(HTTPException) as denied:
            authorize(
                db,
                a["user"],
                a["lodge"].id,
                ReportRequest(a["lodge"].id, a["user"].id, rid, uuid4()),
                "create_task",
            )
        assert denied.value.status_code == 403


def test_clock_handles_south_africa_and_daylight_saving_without_double_runs():
    from app.ai.reports import clock_next

    after = datetime(2026, 11, 8, 5, 0, tzinfo=timezone.utc)
    assert clock_next("daily", 6, 0, 0, "Africa/Johannesburg", after) == datetime(
        2026, 11, 9, 4, 0, tzinfo=timezone.utc
    )
    after = datetime(2026, 3, 8, 5, 0, tzinfo=timezone.utc)
    assert (
        clock_next("daily", 2, 30, 0, "America/New_York", after).date().isoformat()
        == "2026-03-09"
    )
    assert (
        clock_next("weekly", 6, 0, 0, "Africa/Johannesburg", after)
        .astimezone(__import__("zoneinfo").ZoneInfo("Africa/Johannesburg"))
        .weekday()
        == 0
    )


def test_expired_worker_lease_can_be_reclaimed_without_accepting_late_output(scheduled):
    a = scheduled
    s, rid = queued(a)

    class Replaced(TestProvider):
        def complete(self, messages, tools):
            with a["owner"]() as db:
                row = db.get(AIReportRun, rid)
                row.lease_token = uuid4()
                row.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
                db.commit()
            return Completion("PRIVATE LATE OUTPUT")

    assert run(a, rid, Replaced())["status"] == "unavailable"
    with a["owner"]() as db:
        row = db.get(AIReportRun, rid)
        assert row.status == "running"
        assert not db.scalar(
            select(AIMessage.id).where(
                AIMessage.conversation_id == row.conversation_id,
                AIMessage.role == "assistant",
            )
        )
        assert (
            db.scalar(
                select(AIUsage).where(AIUsage.conversation_id == row.conversation_id)
            ).status
            == "failed"
        )
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert run(a, rid)["status"] == "complete"


def test_group_report_includes_each_property_only_with_its_report_capability(
    group_ai, scheduled
):
    a = scheduled
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["second"].id,
                feature_key="ai_daily_summary",
                enabled=True,
                reason="Explicit property report access",
            )
        )
        db.commit()
    _, rid = queued(a, scope="group")
    assert run(a, rid)["status"] == "complete"
    report = a["client"].get(a["reports"] + "/" + rid)
    assert report.status_code == 200, report.text
    assert len(report.json()["message"]["sources"][0]["references"]) == 2
    assert (
        next(x for x in report.json()["insights"] if x["key"] == "overdue_tasks")[
            "count"
        ]
        == 7
    )


def test_saving_or_pausing_schedule_cancels_pending_runs(scheduled):
    a = scheduled
    s, rid = queued(a)
    result = a["client"].post(
        a["reports"] + "/schedules",
        json={"kind": "daily", "enabled": False},
        headers=a["csrf"],
    )
    assert result.status_code == 200, result.text
    with a["owner"]() as db:
        assert db.get(AIReportRun, rid).status == "cancelled"
    assert run(a, rid)["status"] == "skipped"


def test_exhausted_crashed_runs_do_not_stay_running_forever(scheduled):
    a = scheduled
    s, rid = queued(a)
    with a["owner"]() as db:
        row = db.get(AIReportRun, rid)
        row.status = "running"
        row.attempts = 4
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    dispatch_all(a)
    with a["owner"]() as db:
        assert db.get(AIReportRun, rid).status == "failed"


def test_reports_force_rls_and_forged_worker_headers_cannot_authenticate(scheduled):
    from app.db import set_rls_context
    from fastapi.testclient import TestClient
    from app.main import app

    a = scheduled
    s, rid = queued(a)
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), True, str(uuid4()))
        assert (
            not db.scalars(select(AIReportSchedule)).all()
            and not db.scalars(select(AIReportRun)).all()
        )
    client = TestClient(app)
    try:
        result = client.get(
            a["reports"],
            headers={
                "X-Report-Actor": str(a["user"].id),
                "X-Report-Lease": str(uuid4()),
            },
        )
        assert result.status_code == 401
    finally:
        client.close()


def test_lost_publication_acknowledgement_never_requeues_completed_report(scheduled):
    from sqlalchemy.orm import Session, sessionmaker

    a = scheduled
    s, rid = queued(a)
    raised = False

    class LostAck(Session):
        def commit(self):
            nonlocal raised
            publishing = any(
                isinstance(row, AIReportRun) and row.status == "complete"
                for row in self.identity_map.values()
            )
            super().commit()
            if publishing and not raised:
                raised = True
                raise RuntimeError("Isolated lost commit acknowledgement")

    factory = sessionmaker(
        a["application"].kw["bind"], class_=LostAck, expire_on_commit=False
    )
    result = generate(
        a["lodge"].id,
        a["user"].id,
        rid,
        session_factory=factory,
        provider=TestProvider([Completion("Fixture durable report")]),
    )
    assert result["status"] == "unavailable" and raised
    with a["owner"]() as db:
        row = db.get(AIReportRun, rid)
        assert row.status == "complete"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIMessage)
                .where(
                    AIMessage.conversation_id == row.conversation_id,
                    AIMessage.role == "assistant",
                )
            )
            == 1
        )
    assert run(a, rid)["status"] == "skipped"


def test_context_budget_preserves_totals_and_limits_sources_to_retained_rows(
    monkeypatch,
):
    import json
    from app.config import settings
    from app.ai.report_jobs import fit_report_context
    from app.ai.provenance import source_for

    monkeypatch.setattr(settings, "ai_max_context", 4096)
    monkeypatch.setattr(settings, "ai_max_output_tokens", 64)
    facts = [
        {"tool": "get_dashboard_summary", "data": {"metrics": {"overdue_tasks": 51}}},
        {
            "tool": "get_tasks",
            "data": {
                "items": [{"id": str(uuid4()), "title": "x" * 240} for _ in range(50)],
                "partial": False,
                "returned_count": 50,
            },
        },
    ]
    prompt = fit_report_context("daily", {}, facts)
    assert len(json.dumps(prompt, ensure_ascii=False).encode()) <= 4032
    assert facts[0]["data"]["metrics"]["overdue_tasks"] == 51
    assert facts[1]["data"]["partial"] and len(facts[1]["data"]["items"]) < 50
    source = source_for("get_tasks", facts[1]["data"], uuid4())
    assert source["record_ids"] == [row["id"] for row in facts[1]["data"]["items"]]


def test_group_context_budget_recomputes_comparisons_and_actual_contributors(
    monkeypatch,
):
    import json
    from app.config import settings
    from app.ai.report_jobs import fit_report_context
    from app.ai.groups import summarise

    monkeypatch.setattr(settings, "ai_max_context", 4096)
    monkeypatch.setattr(settings, "ai_max_output_tokens", 64)
    items = [
        {
            "lodge_id": str(uuid4()),
            "lodge_name": "Name " + ("x" * 150),
            "metrics": {"overdue_tasks": i + 1},
            "timezone": "Africa/Johannesburg",
        }
        for i in range(20)
    ]
    data = {
        "items": items,
        "comparisons": summarise(items),
        "scope": {
            "group_id": str(uuid4()),
            "group_name": "Collection",
            "lodges": [
                {"lodge_id": r["lodge_id"], "lodge_name": r["lodge_name"]}
                for r in items
            ],
        },
        "partial": False,
    }
    prompt = fit_report_context(
        "daily", {}, [{"tool": "get_group_overview", "data": data}]
    )
    assert len(json.dumps(prompt, ensure_ascii=False).encode()) <= 4032
    assert 0 < len(data["items"]) < 20 and data["partial"]
    assert data["comparisons"] == summarise(data["items"])
    assert set(data["comparisons"]["overdue_tasks"]["contributor_lodge_ids"]) == {
        r["lodge_id"] for r in data["items"]
    }
    assert {r["lodge_id"] for r in data["scope"]["lodges"]} == {
        r["lodge_id"] for r in data["items"]
    }
