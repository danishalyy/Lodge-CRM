from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func, text
from app.ai.providers.base import Completion, ToolCall
from app.models import (
    AIAction,
    Task,
    AuditLog,
    OperationalEvent,
    LodgeEntitlementOverride,
)
from test_ai_foundation import ai, create
from test_ai_groups import group_ai


@pytest.fixture
def acting(ai, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_actions_enabled", True)
    with ai["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=ai["lodge"].id,
                feature_key="ai_actions",
                enabled=True,
                reason="Action test",
            )
        )
        db.commit()
    return ai


def propose(ai, tool="propose_create_task", arguments=None):
    cid = create(ai)
    ai["provider"].replies = [
        Completion(
            tool_calls=[
                ToolCall(
                    "proposal",
                    tool,
                    arguments
                    or {"title": "Inspect the water pump", "priority": "high"},
                )
            ]
        )
    ]
    result = ai["client"].post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Prepare a change for review"},
        headers=ai["csrf"],
    )
    return cid, result


def path(ai, cid, aid):
    return ai["base"] + f"/conversations/{cid}/actions/{aid}"


def reviewed(ai, cid, result):
    assert result.status_code == 200, result.text
    aid = result.json()["actions"][0]["id"]
    root = path(ai, cid, aid)
    review = ai["client"].post(root + "/review", headers=ai["csrf"])
    assert review.status_code == 200, review.text
    return root, review.json()["token"], aid


def test_proposal_never_writes_until_review_and_confirmation_and_retries_are_idempotent(
    acting,
):
    a = acting
    cid, response = propose(a)
    assert response.status_code == 200, response.text
    assert response.json()["actions"][0]["status"] == "pending"
    assert "token" not in str(response.json())
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationalEvent)
                .where(
                    OperationalEvent.lodge_id == a["lodge"].id,
                    OperationalEvent.event_type == "task.created",
                )
            )
            == 0
        )
    root, token, aid = reviewed(a, cid, response)
    assert a["client"].post(root + "/confirm", json={"token": token}).status_code == 403
    assert (
        a["client"]
        .post(root + "/confirm", json={"confirmed": True}, headers=a["csrf"])
        .status_code
        == 422
    )
    reply = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "confirmed"
    again = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert again.json() == reply.json()
    with a["owner"]() as db:
        tasks = db.scalars(select(Task).where(Task.lodge_id == a["lodge"].id)).all()
        assert len(tasks) == 1 and tasks[0].priority == "high"
        row = db.get(AIAction, aid)
        assert row.token_hash and token not in row.token_hash
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.lodge_id == a["lodge"].id,
                    AuditLog.action == "ai.action.confirmed",
                )
            )
            == 1
        )
    history = a["client"].get(a["base"] + f"/conversations/{cid}/messages").json()
    assert history[-1]["actions"][0]["status"] == "confirmed"


@pytest.mark.parametrize(
    "change", ["cancel", "expire", "token", "re_review", "payload"]
)
def test_invalid_confirmation_cannot_write(acting, change):
    a = acting
    cid, response = propose(a)
    root, token, aid = reviewed(a, cid, response)
    body = {"token": token}
    if change == "cancel":
        assert a["client"].post(root + "/cancel", headers=a["csrf"]).status_code == 200
    elif change == "expire":
        with a["owner"]() as db:
            db.get(AIAction, aid).expires_at = datetime.now(timezone.utc) - timedelta(
                seconds=1
            )
            db.commit()
    elif change == "token":
        body["token"] = "x" * 43
    elif change == "re_review":
        assert a["client"].post(root + "/review", headers=a["csrf"]).status_code == 200
    else:
        body["payload"] = {"title": "Tampered"}
    result = a["client"].post(root + "/confirm", json=body, headers=a["csrf"])
    assert result.status_code in [409, 422], result.text
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 0
        )


@pytest.mark.parametrize(
    "revocation", ["feature", "permission", "subscription", "user"]
)
def test_confirmation_rechecks_current_access(acting, revocation):
    from app.models import Membership, Permission, RolePermission, Subscription, User

    a = acting
    cid, response = propose(a)
    root, token, aid = reviewed(a, cid, response)
    with a["owner"]() as db:
        if revocation == "feature":
            row = db.scalar(
                select(LodgeEntitlementOverride).where(
                    LodgeEntitlementOverride.lodge_id == a["lodge"].id,
                    LodgeEntitlementOverride.feature_key == "ai_actions",
                )
            )
            row.enabled = False
        elif revocation == "permission":
            member = db.scalar(
                select(Membership).where(Membership.user_id == a["user"].id)
            )
            pid = db.scalar(select(Permission.id).where(Permission.key == "ai.actions"))
            # A private custom role avoids changing the shared preset for later tests.
            from app.models import CustomRole, CustomRolePermission

            custom = CustomRole(
                lodge_id=a["lodge"].id,
                name="Revoked action",
                base_role_id=member.role_id,
            )
            db.add(custom)
            db.flush()
            member.custom_role_id = custom.id
        elif revocation == "subscription":
            db.get(Subscription, a["lodge"].id).suspended = True
        else:
            db.get(User, a["user"].id).is_active = False
        db.commit()
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code in [401, 403, 409], result.text
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 0
        )


def test_update_proposal_rejects_stale_record_and_preserves_proof_requirements(acting):
    a = acting
    made = a["client"].post(
        "/api/v1/lodges/" + str(a["lodge"].id) + "/tasks",
        json={"title": "Task requiring proof", "proof_required": True},
        headers=a["csrf"],
    )
    assert made.status_code == 200, made.text
    tid = made.json()["id"]
    cid, response = propose(
        a, "propose_update_task", {"task_id": tid, "changes": {"priority": "critical"}}
    )
    root, token, aid = reviewed(a, cid, response)
    with a["owner"]() as db:
        db.get(Task, tid).title = "Changed after review"
        db.commit()
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code == 409, result.text
    with a["owner"]() as db:
        assert db.get(Task, tid).priority == "normal"
    cid, response = propose(
        a, "propose_update_task", {"task_id": tid, "changes": {"status": "completed"}}
    )
    assert response.status_code == 409, response.text


def test_confirmed_update_runs_original_transition_and_linked_effects(acting):
    a = acting
    made = a["client"].post(
        "/api/v1/lodges/" + str(a["lodge"].id) + "/tasks",
        json={"title": "Review update"},
        headers=a["csrf"],
    )
    cid, response = propose(
        a,
        "propose_update_task",
        {
            "task_id": made.json()["id"],
            "changes": {"priority": "critical", "title": "Updated task"},
        },
    )
    root, token, aid = reviewed(a, cid, response)
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code == 200, result.text
    with a["owner"]() as db:
        task = db.get(Task, made.json()["id"])
        assert task.priority == "critical" and task.title == "Updated task"


def test_disabled_actions_and_model_confirmation_tool_are_rejected(ai):
    cid, response = propose(ai)
    assert response.status_code == 403, response.text
    cid, response = propose(ai, "confirm_action", {"confirmed": True})
    assert response.status_code == 422, response.text


def test_proposal_fk_and_identity_injection_rejected(acting):
    a = acting
    for args in [
        {"title": "Wrong lodge", "lodge_id": str(uuid4())},
        {"title": "Wrong actor", "user_id": str(uuid4())},
        {"title": "Missing staff", "assigned_staff_id": str(uuid4())},
    ]:
        _, response = propose(a, arguments=args)
        assert response.status_code in [422, 404], response.text


def test_action_rows_have_private_force_rls(acting):
    from app.db import set_rls_context

    a = acting
    _, response = propose(a)
    assert response.status_code == 200, response.text
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(uuid4()))
        assert not db.scalars(select(AIAction)).all()
        set_rls_context(db, str(uuid4()), False, str(a["user"].id))
        assert not db.scalars(select(AIAction)).all()


@pytest.mark.parametrize("attempt", range(3))
def test_simultaneous_confirmations_create_one_task(acting, attempt):
    from concurrent.futures import ThreadPoolExecutor

    a = acting
    cid, response = propose(a)
    root, token, aid = reviewed(a, cid, response)

    from app.models import AuthSession
    from app.security import token_hash
    from fastapi.testclient import TestClient
    from app.main import app
    import secrets

    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with a["owner"]() as db:
        db.add(
            AuthSession(
                user_id=a["user"].id,
                token_hash=token_hash(raw),
                csrf_hash=token_hash(csrf),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    second = TestClient(app)
    second.cookies.set("lodge_session", raw)
    second.cookies.set("lodge_csrf", csrf)
    clients = [(a["client"], a["csrf"]), (second, {"X-CSRF-Token": csrf})]
    try:

        def confirm(i):
            client, headers = clients[i]
            return client.post(
                root + "/confirm", json={"token": token}, headers=headers
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(confirm, range(2)))
    finally:
        second.close()
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert results[0].json() == results[1].json()
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 1
        )


def test_confirmation_is_atomic_if_existing_mutation_fails(acting, monkeypatch):
    from app import main
    from fastapi import HTTPException

    a = acting
    cid, response = propose(a)
    root, token, aid = reviewed(a, cid, response)
    original = main._create_task_record
    calls = 0

    def failing(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        if calls == 3:
            raise HTTPException(503, "Explicit failure after mutation")
        return result

    monkeypatch.setattr(main, "_create_task_record", failing)
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code == 503, result.text
    with a["owner"]() as db:
        assert db.get(AIAction, aid).status == "pending"
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 0
        )
    monkeypatch.setattr(main, "_create_task_record", original)
    assert (
        a["client"]
        .post(root + "/confirm", json={"token": token}, headers=a["csrf"])
        .status_code
        == 200
    )


@pytest.mark.parametrize(
    "kind", ["propose_create_maintenance", "propose_create_housekeeping"]
)
def test_room_state_and_operational_history_change_only_after_confirmation(
    acting, kind
):
    from app.models import Unit, MaintenanceTicket, HousekeepingJob

    a = acting
    with a["owner"]() as db:
        unit = Unit(
            lodge_id=a["lodge"].id,
            name="Confirmation suite",
            status="ready",
            unit_type="room",
        )
        db.add(unit)
        db.commit()
        uid = str(unit.id)
    args = (
        {"unit_id": uid, "title": "Water leak", "priority": "critical"}
        if kind.endswith("maintenance")
        else {"unit_id": uid, "job_type": "cleaning"}
    )
    cid, response = propose(a, kind, args)
    root, token, aid = reviewed(a, cid, response)
    with a["owner"]() as db:
        assert db.get(Unit, uid).status == "ready"
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code == 200, result.text
    cls = MaintenanceTicket if kind.endswith("maintenance") else HousekeepingJob
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(cls)
                .where(cls.lodge_id == a["lodge"].id)
            )
            == 1
        )
        assert db.get(Unit, uid).status != "ready"


def test_action_cannot_be_reviewed_from_another_conversation(acting):
    a = acting
    cid, response = propose(a)
    root, token, aid = reviewed(a, cid, response)
    other = create(a)
    assert (
        a["client"].post(path(a, other, aid) + "/review", headers=a["csrf"]).status_code
        == 404
    )


def test_model_cannot_supply_a_group_scope(acting):
    from app.models import AIConversation

    a = acting
    cid = create(a)
    # Scope selection cannot be supplied as a tool argument, even by the model.
    _, response = propose(a, arguments={"title": "Group change", "scope": "group"})
    assert response.status_code == 422, response.text


def test_group_conversation_does_not_offer_or_accept_actions(group_ai, monkeypatch):
    from app.config import settings
    from test_ai_groups import create_group

    a = group_ai
    monkeypatch.setattr(settings, "ai_actions_enabled", True)
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key="ai_actions",
                enabled=True,
                reason="test",
            )
        )
        db.commit()
    cid = create_group(a)
    a["provider"].replies = [
        Completion(
            tool_calls=[
                ToolCall(
                    "bad-group-action", "propose_create_task", {"title": "Group write"}
                )
            ]
        )
    ]
    result = a["client"].post(
        a["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Attempt group action"},
        headers=a["csrf"],
    )
    assert result.status_code == 403, result.text
    assert all(
        not t["function"]["name"].startswith("propose_")
        for t in a["provider"].calls[0][1]
    )


def test_action_only_role_can_propose_without_exposing_unreadable_room_names(acting):
    from app.models import (
        CustomRole,
        CustomRolePermission,
        Membership,
        Permission,
        Unit,
    )

    a = acting
    with a["owner"]() as db:
        member = db.scalar(select(Membership).where(Membership.user_id == a["user"].id))
        role = CustomRole(
            lodge_id=a["lodge"].id, name="Action only", base_role_id=member.role_id
        )
        db.add(role)
        db.flush()
        for permission in db.scalars(
            select(Permission).where(
                Permission.key.in_(["ai.use", "ai.actions", "tasks.manage"])
            )
        ):
            db.add(
                CustomRolePermission(
                    lodge_id=a["lodge"].id,
                    custom_role_id=role.id,
                    permission_id=permission.id,
                )
            )
        member.custom_role_id = role.id
        unit = Unit(lodge_id=a["lodge"].id, name="PRIVATE ROOM LABEL", unit_type="room")
        db.add(unit)
        db.commit()
        uid = str(unit.id)
    tools = a["client"].get(a["base"] + "/status").json()["tools"]
    assert [t["name"] for t in tools] == ["propose_create_task"]
    cid, response = propose(
        a, arguments={"title": "Inspect selected room", "unit_id": uid}
    )
    assert response.status_code == 200, response.text
    assert "PRIVATE ROOM LABEL" not in response.text
    assert any(
        f["key"] == "unit_id" and f["value"] == uid
        for f in response.json()["actions"][0]["preview"]["fields"]
    )


def test_assignee_notifications_are_not_emitted_by_preparation_or_review(acting):
    from app.models import StaffProfile, Notification

    a = acting
    with a["owner"]() as db:
        staff = StaffProfile(lodge_id=a["lodge"].id, full_name="Assigned colleague")
        db.add(staff)
        db.commit()
        sid = str(staff.id)
    cid, response = propose(
        a, arguments={"title": "Inspect water supply", "assigned_staff_id": sid}
    )
    root, token, aid = reviewed(a, cid, response)
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.lodge_id == a["lodge"].id)
            )
            == 0
        )
    result = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert result.status_code == 200, result.text
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.lodge_id == a["lodge"].id,
                    Notification.notification_type == "task.assigned",
                )
            )
            == 1
        )


def test_action_clarification_does_not_publish_unsourced_claims_or_execute(acting):
    from app.ai.actions import CLARIFICATION

    a = acting
    cid = create(a)
    a["provider"].replies = [
        Completion("I created 350 tasks and deleted all guest records.")
    ]
    result = a["client"].post(
        a["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Prepare a change"},
        headers=a["csrf"],
    )
    assert result.status_code == 200, result.text
    assert result.json()["content"] == CLARIFICATION and result.json()["sources"] == []
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AIAction)
                .where(AIAction.lodge_id == a["lodge"].id)
            )
            == 0
        )
