"""Group comparisons use real scoped PostgreSQL, never a global database role."""

from datetime import datetime, date, timedelta, timezone
from uuid import uuid4
import json
import pytest
from sqlalchemy import select, text
from app.models import (
    LodgeGroup,
    Lodge,
    Membership,
    Role,
    Subscription,
    Task,
    MaintenanceTicket,
    LodgeEntitlementOverride,
    AIConversation,
    AIMessage,
    AIUsage,
    Permission,
    CustomRole,
    CustomRolePermission,
    Unit,
    HousekeepingJob,
    User,
)
from app.ai.providers.base import Completion, ToolCall
from test_ai_foundation import ai


@pytest.fixture
def group_ai(ai):
    with ai["owner"]() as db:
        group = LodgeGroup(
            name="Group AI " + uuid4().hex, admin_user_id=ai["user"].id, is_active=True
        )
        othergroup = LodgeGroup(
            name="Other owned group " + uuid4().hex,
            admin_user_id=ai["user"].id,
            is_active=True,
        )
        db.add_all([group, othergroup])
        db.flush()
        db.get(Lodge, ai["lodge"].id).group_id = group.id
        db.flush()
        role = db.scalar(select(Role).where(Role.key == "group_admin"))
        db.scalar(
            select(Membership).where(Membership.user_id == ai["user"].id)
        ).role_id = role.id
        second = Lodge(
            name="Second property " + uuid4().hex,
            group_id=group.id,
            timezone="Africa/Johannesburg",
        )
        unassigned = Lodge(name="UNASSIGNED PROPERTY " + uuid4().hex, group_id=group.id)
        foreign = Lodge(
            name="OTHER GROUP PROPERTY " + uuid4().hex, group_id=othergroup.id
        )
        db.add_all([second, unassigned, foreign])
        db.flush()
        for lodge in (second, foreign):
            db.add(
                Membership(user_id=ai["user"].id, lodge_id=lodge.id, role_id=role.id)
            )
            db.add(
                Subscription(
                    lodge_id=lodge.id,
                    package="Standard",
                    start_date=date.today() - timedelta(days=1),
                    expiry_date=date.today() + timedelta(days=60),
                )
            )
        for lodge in (ai["lodge"], second, foreign):
            db.add(
                LodgeEntitlementOverride(
                    lodge_id=lodge.id,
                    feature_key="advanced_ai",
                    enabled=True,
                    reason="Group test",
                )
            )
            if lodge.id != ai["lodge"].id:
                db.add(
                    LodgeEntitlementOverride(
                        lodge_id=lodge.id,
                        feature_key="ai",
                        enabled=True,
                        reason="Group test",
                    )
                )
        for lodge, count in [
            (ai["lodge"], 2),
            (second, 5),
            (unassigned, 44),
            (foreign, 77),
        ]:
            for _ in range(count):
                db.add(
                    Task(
                        lodge_id=lodge.id,
                        title="PRIVATE TASK TITLE",
                        description="private@example.com password=secret",
                        due_at=datetime.now(timezone.utc) - timedelta(days=1),
                        created_by_user_id=ai["user"].id,
                    )
                )
        for lodge, count in [(ai["lodge"], 1), (second, 3)]:
            for _ in range(count):
                db.add(
                    MaintenanceTicket(
                        lodge_id=lodge.id,
                        title="PRIVATE MAINTENANCE",
                        created_by_user_id=ai["user"].id,
                    )
                )
            unit = Unit(lodge_id=lodge.id, name="Private unit")
            db.add(unit)
            db.flush()
            db.add(
                HousekeepingJob(
                    lodge_id=lodge.id,
                    unit_id=unit.id,
                    job_type="cleaning",
                    status="awaiting_inspection",
                    created_by_user_id=ai["user"].id,
                )
            )
        db.commit()
    ai.update(group=group, second=second, foreign=foreign, unassigned=unassigned)
    return ai


def create_group(ai, scope="group"):
    response = ai["client"].post(
        ai["base"] + "/conversations", json={"scope": scope}, headers=ai["csrf"]
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def ask(ai, name="get_group_overview", args=None, cid=None, rid=None):
    ai["provider"].replies = [
        Completion(tool_calls=[ToolCall("group", name, args or {})]),
        Completion("Test-only group explanation"),
    ]
    cid = cid or create_group(ai)
    rid = rid or str(uuid4())
    response = ai["client"].post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": rid, "content": "Compare my lodges"},
        headers=ai["csrf"],
    )
    return response, cid, rid


def payload(ai):
    return json.loads(ai["provider"].calls[-1][0][-1]["content"])


def test_group_overview_has_exact_counts_contributors_and_isolated_sources(group_ai):
    ai = group_ai
    response, cid, rid = ask(ai)
    assert response.status_code == 200, response.text
    data = payload(ai)
    assert len(data["items"]) == 2
    totals = data["comparisons"]
    assert totals["overdue_tasks"]["total"] == 7
    assert totals["overdue_tasks"]["maximum"] == 5
    assert totals["overdue_tasks"]["highest_lodge_ids"] == [str(ai["second"].id)]
    assert totals["maintenance_open"]["total"] == 4
    assert totals["housekeeping_awaiting_inspection"]["total"] == 2
    assert set(totals["overdue_tasks"]["contributor_lodge_ids"]) == {
        str(ai["lodge"].id),
        str(ai["second"].id),
    }
    sent = json.dumps(ai["provider"].calls)
    for hidden in [
        "PRIVATE TASK TITLE",
        "PRIVATE MAINTENANCE",
        "private@example.com",
        "UNASSIGNED PROPERTY",
        "OTHER GROUP PROPERTY",
    ]:
        assert hidden not in sent
    assert {tool["function"]["name"] for tool in ai["provider"].calls[0][1]} == {
        "get_group_overview",
        "get_group_report_metrics",
    }
    source = response.json()["sources"][0]
    assert source["kind"] == "group" and source["group_id"] == str(ai["group"].id)
    assert {r["lodge_id"] for r in source["references"]} == {
        str(ai["lodge"].id),
        str(ai["second"].id),
    }
    assert (
        source["contributors"]["overdue_tasks"]
        == totals["overdue_tasks"]["contributor_lodge_ids"]
    )
    # Normal history and group history do not share a conversation list.
    assert ai["client"].get(ai["base"] + "/conversations").json() == []
    assert [
        r["id"]
        for r in ai["client"].get(ai["base"] + "/conversations?scope=group").json()
    ] == [cid]
    assert (
        ai["client"].get(ai["base"] + f"/conversations/{cid}/messages").status_code
        == 200
    )
    before = len(ai["provider"].calls)
    replay = ai["client"].post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": rid, "content": "Retry"},
        headers=ai["csrf"],
    )
    assert replay.status_code == 200 and len(ai["provider"].calls) == before
    with ai["owner"]() as db:
        conv = db.get(AIConversation, cid)
        assert conv.scope_type == "group" and conv.group_id == ai["group"].id
        assert (
            db.scalar(select(AIUsage).where(AIUsage.conversation_id == cid)).lodge_id
            == ai["lodge"].id
        )


def test_group_reports_use_same_explicit_utc_period_and_deterministic_cohort_counts(
    group_ai,
):
    ai = group_ai
    with ai["owner"]() as db:
        for lodge in (ai["lodge"], ai["second"]):
            db.add(
                Task(
                    lodge_id=lodge.id,
                    title="In period",
                    created_at=datetime(2026, 10, 19, 23, 59, tzinfo=timezone.utc),
                    created_by_user_id=ai["user"].id,
                )
            )
            db.add(
                Task(
                    lodge_id=lodge.id,
                    title="Outside period",
                    created_at=datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc),
                    created_by_user_id=ai["user"].id,
                )
            )
        db.commit()
    response, _, _ = ask(
        ai,
        "get_group_report_metrics",
        {"start_date": "2026-10-19", "end_date": "2026-10-19"},
    )
    assert response.status_code == 200, response.text
    data = payload(ai)
    assert data["comparisons"]["tasks_created"]["total"] == 2
    assert all(
        row["period"]
        == {
            "start_date": "2026-10-19",
            "end_date": "2026-10-19",
            "timestamp_timezone": "UTC",
        }
        for row in data["items"]
    )
    assert not any(
        "cost" in key or "rate" in key or "average" in key
        for key in data["comparisons"]
    )


@pytest.mark.parametrize(
    "blocked",
    ["ai", "advanced_ai", "expired", "suspended", "no_subscription", "permission"],
)
def test_group_skips_ineligible_property_without_fabricating_zero_metrics(
    group_ai, blocked
):
    ai = group_ai
    with ai["owner"]() as db:
        lid = ai["second"].id
        if blocked in {"ai", "advanced_ai"}:
            db.get(
                LodgeEntitlementOverride, {"lodge_id": lid, "feature_key": blocked}
            ).enabled = False
        elif blocked == "expired":
            db.get(Subscription, lid).expiry_date = date.today() - timedelta(days=1)
        elif blocked == "suspended":
            db.get(Subscription, lid).suspended = True
        elif blocked == "no_subscription":
            db.delete(db.get(Subscription, lid))
        else:
            custom = CustomRole(
                lodge_id=lid,
                name="No group intelligence",
                base_role_id=db.scalar(
                    select(Role.id).where(Role.key == "group_admin")
                ),
                is_active=True,
            )
            db.add(custom)
            db.flush()
            db.add(
                CustomRolePermission(
                    lodge_id=lid,
                    custom_role_id=custom.id,
                    permission_id=db.scalar(
                        select(Permission.id).where(Permission.key == "ai.use")
                    ),
                )
            )
            db.scalar(
                select(Membership).where(
                    Membership.user_id == ai["user"].id, Membership.lodge_id == lid
                )
            ).custom_role_id = custom.id
        db.commit()
    response, _, _ = ask(ai)
    assert response.status_code == 200, response.text
    data = payload(ai)
    assert [r["lodge_id"] for r in data["items"]] == [str(ai["lodge"].id)]
    assert data["excluded_count"] == 1 and data["partial"]
    assert data["comparisons"]["overdue_tasks"]["total"] == 2
    assert "Second property" not in json.dumps(ai["provider"].calls)


def test_each_metric_has_its_own_permission_filtered_contributors(group_ai):
    ai = group_ai
    with ai["owner"]() as db:
        lid = ai["second"].id
        custom = CustomRole(
            lodge_id=lid,
            name="Limited operational AI",
            base_role_id=db.scalar(select(Role.id).where(Role.key == "group_admin")),
            is_active=True,
        )
        db.add(custom)
        db.flush()
        for key in ["ai.use", "ai.group.view", "dashboard.view", "maintenance.view"]:
            db.add(
                CustomRolePermission(
                    lodge_id=lid,
                    custom_role_id=custom.id,
                    permission_id=db.scalar(
                        select(Permission.id).where(Permission.key == key)
                    ),
                )
            )
        db.scalar(
            select(Membership).where(
                Membership.user_id == ai["user"].id, Membership.lodge_id == lid
            )
        ).custom_role_id = custom.id
        db.commit()
    response, _, _ = ask(ai)
    assert response.status_code == 200, response.text
    data = payload(ai)
    second = next(r for r in data["items"] if r["lodge_id"] == str(lid))
    assert "overdue_tasks" not in second["metrics"]
    assert data["comparisons"]["overdue_tasks"]["contributor_lodge_ids"] == [
        str(ai["lodge"].id)
    ]
    assert data["comparisons"]["maintenance_open"]["total"] == 4


@pytest.mark.parametrize(
    "change", ["membership", "group", "feature", "permission", "plan", "ownership"]
)
def test_saved_group_answers_and_retries_recheck_every_property(group_ai, change):
    ai = group_ai
    response, cid, rid = ask(ai)
    assert response.status_code == 200, response.text
    with ai["owner"]() as db:
        lid = ai["second"].id
        if change == "membership":
            db.scalar(
                select(Membership).where(
                    Membership.user_id == ai["user"].id, Membership.lodge_id == lid
                )
            ).is_active = False
        elif change == "group":
            db.get(Lodge, lid).group_id = ai["foreign"].group_id
        elif change == "feature":
            db.get(
                LodgeEntitlementOverride,
                {"lodge_id": lid, "feature_key": "advanced_ai"},
            ).enabled = False
        elif change == "permission":
            custom = CustomRole(
                lodge_id=lid,
                name="Changed grants",
                base_role_id=db.scalar(
                    select(Role.id).where(Role.key == "group_admin")
                ),
                is_active=True,
            )
            db.add(custom)
            db.flush()
            db.scalar(
                select(Membership).where(
                    Membership.user_id == ai["user"].id, Membership.lodge_id == lid
                )
            ).custom_role_id = custom.id
        elif change == "plan":
            db.get(Subscription, lid).suspended = True
        else:
            db.get(LodgeGroup, ai["group"].id).is_active = False
        db.commit()
    history = ai["client"].get(ai["base"] + f"/conversations/{cid}/messages")
    assert (
        history.status_code in {401, 403, 409}
        and "group explanation" not in history.text
    )
    replay = ai["client"].post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": rid, "content": "Retry"},
        headers=ai["csrf"],
    )
    assert (
        replay.status_code in {401, 403, 409} and "group explanation" not in replay.text
    )


def test_group_membership_change_during_inference_refuses_answer(group_ai):
    ai = group_ai
    from app.main import app
    from app.ai.routes import provider_dependency

    class RevokingProvider:
        calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return Completion(
                    tool_calls=[ToolCall("read", "get_group_overview", {})]
                )
            with ai["owner"]() as db:
                db.get(
                    LodgeEntitlementOverride,
                    {"lodge_id": ai["second"].id, "feature_key": "advanced_ai"},
                ).enabled = False
                db.commit()
            return Completion("STALE PRIVILEGED ANSWER")

    app.dependency_overrides[provider_dependency] = lambda: RevokingProvider()
    cid = create_group(ai)
    response = ai["client"].post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Compare"},
        headers=ai["csrf"],
    )
    assert response.status_code == 409 and "STALE PRIVILEGED" not in response.text


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_group_overview", {"lodge_id": str(uuid4())}),
        ("get_group_overview", {"group_id": str(uuid4())}),
        ("get_group_report_metrics", {"start_date": "2026-02-30"}),
        (
            "get_group_report_metrics",
            {"start_date": "2020-01-01", "end_date": "2026-01-01"},
        ),
        (
            "get_group_report_metrics",
            {"start_date": "2026-10-20", "end_date": "2026-10-19"},
        ),
        ("get_tasks", {}),
        ("search_lodge_knowledge", {"query": "Private SOP"}),
        ("fetch_url", {"url": "http://169.254.169.254"}),
    ],
)
def test_group_model_cannot_choose_scope_or_use_granular_or_arbitrary_tools(
    group_ai, name, args
):
    reply, _, _ = ask(group_ai, name, args)
    assert reply.status_code in {403, 422}, reply.text


def test_lodge_admin_cannot_create_group_conversation_or_forge_group_identity(ai):
    reply = ai["client"].post(
        ai["base"] + "/conversations", json={"scope": "group"}, headers=ai["csrf"]
    )
    assert reply.status_code == 403
    for body in [
        {"scope": "group", "group_id": str(uuid4())},
        {"scope": "group", "lodge_ids": [str(uuid4())]},
        {"scope": "platform"},
    ]:
        assert (
            ai["client"]
            .post(ai["base"] + "/conversations", json=body, headers=ai["csrf"])
            .status_code
            == 422
        )


def test_group_status_scope_and_cross_lodge_private_history_boundaries(group_ai):
    ai = group_ai
    status = ai["client"].get(ai["base"] + "/status?scope=group")
    assert status.status_code == 200, status.text
    body = status.json()
    assert (
        body["scope"]["group_id"] == str(ai["group"].id)
        and not body["knowledge_enabled"]
    )
    assert {p["lodge_id"] for p in body["scope"]["lodges"]} == {
        str(ai["lodge"].id),
        str(ai["second"].id),
    }
    cid = create_group(ai)
    assert (
        ai["client"]
        .get(
            ai["base"].replace(str(ai["lodge"].id), str(ai["second"].id))
            + f"/conversations/{cid}/messages"
        )
        .status_code
        == 404
    )
    assert (
        ai["client"]
        .post(ai["base"] + "/conversations", json={"scope": "group"})
        .status_code
        == 403
    )
    from app.db import set_rls_context

    with ai["application"]() as db:
        set_rls_context(db, str(ai["lodge"].id), True, str(uuid4()))
        assert not db.scalar(select(AIConversation.id).where(AIConversation.id == cid))


def test_group_context_truncation_recomputes_totals_and_contributors(
    group_ai, monkeypatch
):
    from app.config import settings
    from app.ai.groups import summarise

    ai = group_ai
    reply, _, _ = ask(ai)
    assert reply.status_code == 200, reply.text
    result = payload(ai)
    assert len(result["items"]) == 2
    smaller = {
        **result,
        "items": result["items"][:1],
        "comparisons": summarise(result["items"][:1]),
        "returned_count": 1,
        "partial": True,
    }
    overhead = len(
        json.dumps(
            [ai["provider"].calls[0][0][:2], ai["provider"].calls[0][1]],
            ensure_ascii=False,
        ).encode()
    )
    limit = (
        overhead
        + settings.ai_max_output_tokens
        + 1024
        + len(json.dumps(smaller, ensure_ascii=False).encode())
        + 80
    )
    monkeypatch.setattr(settings, "ai_max_context", limit)
    reply, _, _ = ask(ai)
    assert reply.status_code == 200, reply.text
    actual = payload(ai)
    assert actual["partial"] and len(actual["items"]) == 1
    retained = actual["items"][0]
    assert (
        actual["comparisons"]["overdue_tasks"]["total"]
        == retained["metrics"]["overdue_tasks"]
    )
    assert actual["comparisons"]["overdue_tasks"]["contributor_lodge_ids"] == [
        retained["lodge_id"]
    ]
    assert reply.json()["sources"][0]["contributors"]["overdue_tasks"] == [
        retained["lodge_id"]
    ]


def test_group_property_limit_refuses_instead_of_silently_omitting_lodges(group_ai):
    ai = group_ai
    with ai["owner"]() as db:
        role = db.scalar(select(Role.id).where(Role.key == "group_admin"))
        for _ in range(19):
            lodge = Lodge(name="Bounded group " + uuid4().hex, group_id=ai["group"].id)
            db.add(lodge)
            db.flush()
            db.add(Membership(lodge_id=lodge.id, user_id=ai["user"].id, role_id=role))
        db.commit()
    assert ai["client"].get(ai["base"] + "/status?scope=group").status_code == 413
    response = ai["client"].post(
        ai["base"] + "/conversations", json={"scope": "group"}, headers=ai["csrf"]
    )
    assert response.status_code == 413 and not ai["provider"].calls


@pytest.mark.parametrize("blocked", ["permission", "feature"])
def test_group_housekeeping_reports_require_report_access_as_well_as_module_access(
    group_ai, blocked
):
    ai = group_ai
    with ai["owner"]() as db:
        lid = ai["second"].id
        if blocked == "permission":
            custom = CustomRole(
                lodge_id=lid,
                name="Current housekeeping only",
                base_role_id=db.scalar(
                    select(Role.id).where(Role.key == "group_admin")
                ),
                is_active=True,
            )
            db.add(custom)
            db.flush()
            for key in ["ai.use", "ai.group.view", "housekeeping.view"]:
                db.add(
                    CustomRolePermission(
                        lodge_id=lid,
                        custom_role_id=custom.id,
                        permission_id=db.scalar(
                            select(Permission.id).where(Permission.key == key)
                        ),
                    )
                )
            db.scalar(
                select(Membership).where(
                    Membership.user_id == ai["user"].id, Membership.lodge_id == lid
                )
            ).custom_role_id = custom.id
        else:
            db.add(
                LodgeEntitlementOverride(
                    lodge_id=lid,
                    feature_key="reports",
                    enabled=False,
                    reason="Report access test",
                )
            )
        db.commit()
    response, _, _ = ask(ai, "get_group_report_metrics")
    assert response.status_code == 200, response.text
    data = payload(ai)
    second = next(row for row in data["items"] if row["lodge_id"] == str(lid))
    assert second["metrics"] == {} and second["period"]["timestamp_timezone"] == "UTC"
    assert data["partial"]
    assert data["comparisons"]["housekeeping_created"]["contributor_lodge_ids"] == [
        str(ai["lodge"].id)
    ]
    ref = next(
        r
        for r in response.json()["sources"][0]["references"]
        if r["lodge_id"] == str(lid)
    )
    assert ref["metric_keys"] == []
