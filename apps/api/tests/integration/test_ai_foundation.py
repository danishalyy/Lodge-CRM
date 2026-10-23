from uuid import uuid4
from datetime import date, timedelta
import pytest
from sqlalchemy import select, text
from app.ai.providers.base import Completion, ProviderUnavailable


@pytest.fixture
def ai(account, monkeypatch):
    from app.config import settings
    from app.feature_catalog import BUILT
    from app.models import LodgeEntitlementOverride
    from app.main import app
    from app.ai.routes import provider_dependency
    from app.ai.providers.testing import TestProvider

    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_provider", "test")
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setitem(
        BUILT, "ai", ("Lodge AI", "Foundation under test", "Reports and AI")
    )
    with account["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=account["lodge"].id,
                feature_key="ai",
                enabled=True,
                reason="Temporary test fixture",
            )
        )
        db.commit()
    provider = TestProvider(
        [Completion("Connection test response", input_tokens=11, output_tokens=5)]
    )
    app.dependency_overrides[provider_dependency] = lambda: provider
    try:
        yield {
            **account,
            "provider": provider,
            "base": f"/api/v1/lodges/{account['lodge'].id}/ai",
        }
    finally:
        app.dependency_overrides.pop(provider_dependency, None)


def create(ai):
    result = ai["client"].post(ai["base"] + "/conversations", headers=ai["csrf"])
    assert result.status_code == 200, result.text
    return result.json()["id"]


def test_ai_persists_private_turn_and_usage_and_idempotency(ai):
    from app.models import AIUsage, AIMessage, AuditLog

    c = ai["client"]
    cid = create(ai)
    body = {"request_id": str(uuid4()), "content": "Connection check"}
    path = ai["base"] + f"/conversations/{cid}/messages"
    assert c.post(path, json=body).status_code == 403
    reply = c.post(path, json=body, headers=ai["csrf"])
    assert reply.status_code == 200, reply.text
    again = c.post(path, json=body, headers=ai["csrf"])
    assert again.json() == reply.json() and len(ai["provider"].calls) == 1
    history = c.get(path).json()
    assert [x["role"] for x in history] == ["user", "assistant"]
    with ai["owner"]() as db:
        usage = db.scalar(select(AIUsage).where(AIUsage.conversation_id == cid))
        assert (
            usage.status == "complete"
            and usage.input_tokens == 11
            and usage.output_tokens == 5
        )
        assert db.scalar(
            select(AuditLog).where(
                AuditLog.action == "ai.request.completed",
                AuditLog.lodge_id == ai["lodge"].id,
            )
        )
    assert (
        c.post(
            path, json={**body, "lodge_id": str(uuid4())}, headers=ai["csrf"]
        ).status_code
        == 422
    )


def test_ai_denies_other_lodge_and_private_owner_rls(ai):
    from app.models import Lodge, AIConversation, User
    from app.db import set_rls_context

    c = ai["client"]
    cid = create(ai)
    with ai["owner"]() as db:
        other = Lodge(name="Foreign AI " + uuid4().hex)
        db.add(other)
        db.commit()
    assert (
        c.get(f"/api/v1/lodges/{other.id}/ai/conversations/{cid}/messages").status_code
        == 403
    )
    with ai["application"]() as db:
        set_rls_context(db, str(other.id), False, str(ai["user"].id))
        assert not db.scalars(select(AIConversation)).all()
        set_rls_context(db, str(ai["lodge"].id), True, str(uuid4()))
        assert not db.scalars(
            select(AIConversation)
        ).all(), "Super context must not bypass private owner RLS"
        flags = db.execute(
            text(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname LIKE 'ai_%' AND relkind='r'"
            )
        ).all()
        assert len(flags) == 4 and all(x == (True, True) for x in flags)


def test_ai_rechecks_access_and_subscriptions(ai):
    from app.models import (
        Subscription,
        RolePermission,
        Membership,
        Role,
        Permission,
        CustomRole,
        CustomRolePermission,
    )

    c = ai["client"]
    cid = create(ai)
    path = ai["base"] + f"/conversations/{cid}/messages"
    with ai["owner"]() as db:
        sub = db.get(Subscription, ai["lodge"].id)
        sub.expiry_date = date.today() - timedelta(days=1)
        sub.start_date = date.today() - timedelta(days=20)
        db.commit()
    assert (
        c.post(
            path,
            json={"request_id": str(uuid4()), "content": "Check"},
            headers=ai["csrf"],
        ).status_code
        == 403
    )
    assert (
        c.get(path).status_code == 409
    )  # ACL fingerprint changed; old context is not replayed.
    with ai["owner"]() as db:
        sub = db.get(Subscription, ai["lodge"].id)
        sub.expiry_date = date.today() + timedelta(days=20)
        db.commit()
    assert c.get(path).status_code == 409


def test_ai_outage_isolated_and_failures_recorded(ai):
    from app.models import AIUsage

    ai["provider"].replies = [ProviderUnavailable()]
    c = ai["client"]
    cid = create(ai)
    response = c.post(
        ai["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Check"},
        headers=ai["csrf"],
    )
    assert response.status_code == 503, response.text
    assert c.get("/api/v1/auth/me").status_code == 200
    assert c.get(f"/api/v1/lodges/{ai['lodge'].id}/guests").status_code == 200
    with ai["owner"]() as db:
        assert (
            db.scalar(select(AIUsage).where(AIUsage.conversation_id == cid)).status
            == "failed"
        )


def test_ai_test_provider_refused_outside_tests_and_features_enforced(ai, monkeypatch):
    from app.config import settings
    from app.models import LodgeEntitlementOverride
    from app.ai.configuration import configuration_state, get_provider

    monkeypatch.setattr(settings, "app_env", "production")
    assert configuration_state() == "misconfigured"
    with pytest.raises(ProviderUnavailable):
        get_provider()
    monkeypatch.setattr(settings, "app_env", "test")
    with ai["owner"]() as db:
        db.get(
            LodgeEntitlementOverride, {"lodge_id": ai["lodge"].id, "feature_key": "ai"}
        ).enabled = False
        db.commit()
    assert ai["client"].get(ai["base"] + "/status").status_code == 403


def test_ai_permission_removal_blocks_history(ai):
    from app.models import Membership, Role

    cid = create(ai)
    with ai["owner"]() as db:
        member = db.scalar(
            select(Membership).where(Membership.user_id == ai["user"].id)
        )
        member.role_id = db.scalar(select(Role.id).where(Role.key == "read_only"))
        db.commit()
    assert (
        ai["client"].get(ai["base"] + f"/conversations/{cid}/messages").status_code
        == 403
    )


def test_group_ai_is_explicit_lodge_scope_without_platform_bypass(ai):
    from app.models import LodgeGroup, Lodge, Membership, Role, Subscription, User

    c = ai["client"]
    with ai["owner"]() as db:
        group = LodgeGroup(
            name="AI group " + uuid4().hex, admin_user_id=ai["user"].id, is_active=True
        )
        db.add(group)
        db.flush()
        lodge = db.get(Lodge, ai["lodge"].id)
        lodge.group_id = group.id
        member = db.scalar(
            select(Membership).where(Membership.user_id == ai["user"].id)
        )
        role = db.scalar(select(Role).where(Role.key == "group_admin"))
        member.role_id = role.id
        second = Lodge(name="Assigned AI " + uuid4().hex, group_id=group.id)
        foreign = Lodge(name="Foreign group AI " + uuid4().hex)
        db.add_all([second, foreign])
        db.flush()
        db.add_all(
            [
                Membership(user_id=ai["user"].id, lodge_id=second.id, role_id=role.id),
                Subscription(
                    lodge_id=second.id,
                    package="Standard",
                    start_date=date.today() - timedelta(days=1),
                    expiry_date=date.today() + timedelta(days=20),
                ),
            ]
        )
        db.commit()
    cid = create(ai)
    assert c.get(f"/api/v1/lodges/{second.id}/ai/conversations").json() == []
    assert (
        c.get(f"/api/v1/lodges/{second.id}/ai/conversations/{cid}/messages").status_code
        == 404
    )
    assert c.get(f"/api/v1/lodges/{foreign.id}/ai/status").status_code == 403
    assert c.get("/api/v1/platform/plans").status_code == 403


def test_ai_explicitly_denies_automatic_super_admin_tenant_inference(ai):
    from app.models import User
    from datetime import datetime, timezone

    with ai["owner"]() as db:
        user = db.get(User, ai["user"].id)
        user.is_super_admin = True
        user.mfa_enabled_at = datetime.now(timezone.utc)
        db.commit()
    response = ai["client"].get(ai["base"] + "/status")
    assert response.status_code == 403 and "support access" in response.text
