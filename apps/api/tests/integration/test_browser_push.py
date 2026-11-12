"""Opt-in, encrypted subscriptions, privacy, authority and durable push delivery."""

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone, date
from types import SimpleNamespace
from uuid import uuid4
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select
from app import push_service as service
from app.models import (
    PushSubscription,
    PushPreference,
    PushDelivery,
    Task,
    AuthSession,
    Membership,
    Role,
    NotificationRecipient,
    LodgeEntitlementOverride,
    Subscription,
    User,
)
from app.db import set_rls_context
from app.notification_service import create_notification


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def browser_device():
    key = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/" + uuid4().hex,
        "keys": {"p256dh": b64(key), "auth": b64(secrets.token_bytes(16))},
    }


@pytest.fixture
def push(account, monkeypatch):
    a = account
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(
        service.settings,
        "push_vapid_private_key",
        b64(private.private_numbers().private_value.to_bytes(32, "big")),
    )
    monkeypatch.setattr(
        service.settings,
        "push_vapid_public_key",
        b64(
            private.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        ),
    )
    monkeypatch.setattr(
        service.settings, "push_encryption_key", Fernet.generate_key().decode()
    )
    monkeypatch.setattr(
        service.settings, "push_vapid_subject", "mailto:security@example.test"
    )
    a.update(base=f"/api/v1/lodges/{a['lodge'].id}/push", device=browser_device())
    return a


def register(a):
    r = a["client"].post(
        a["base"] + "/subscriptions", json=a["device"], headers=a["csrf"]
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def notice(a, recipient=None):
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        task = Task(
            lodge_id=a["lodge"].id,
            title="Guest name and private details",
            created_by_user_id=a["user"].id,
        )
        db.add(task)
        db.flush()
        n = create_notification(
            db,
            lodge_id=a["lodge"].id,
            notification_type="task.assigned",
            severity="normal",
            title="Sensitive title",
            body="Guest personal data",
            resource_type="task",
            resource_id=task.id,
            recipient_user_ids=[recipient or a["user"].id],
        )
        db.commit()
        return n.id


def test_configuration_and_keys_are_private(push):
    a = push
    r = a["client"].get(a["base"] + "/preferences")
    assert r.status_code == 200, r.text
    assert r.json()["configured"] and not r.json()["enabled"]
    assert (
        service.settings.push_vapid_private_key not in r.text
        and service.settings.push_encryption_key not in r.text
    )
    key = register(a)
    with a["owner"]() as db:
        sub = db.get(PushSubscription, key)
        assert a["device"]["endpoint"] not in sub.encrypted_subscription
        assert a["device"]["keys"]["auth"] not in sub.encrypted_subscription
        assert db.get(PushPreference, (a["lodge"].id, a["user"].id)).enabled


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1/private",
        "http://fcm.googleapis.com/a",
        "https://fcm.googleapis.com:8443/a",
        "https://user:pass@fcm.googleapis.com/a",
        "https://attacker.test/a",
    ],
)
def test_untrusted_push_destinations_are_rejected(push, endpoint):
    a = push
    r = a["client"].post(
        a["base"] + "/subscriptions",
        json={**a["device"], "endpoint": endpoint},
        headers=a["csrf"],
    )
    assert r.status_code == 422


def test_invalid_browser_keys_and_csrf_are_rejected(push):
    a = push
    body = {**a["device"], "keys": {"p256dh": "abc", "auth": "abc"}}
    assert (
        a["client"]
        .post(a["base"] + "/subscriptions", json=body, headers=a["csrf"])
        .status_code
        == 422
    )
    assert (
        a["client"].post(a["base"] + "/subscriptions", json=a["device"]).status_code
        == 403
    )


def test_unconfigured_push_does_not_prevent_core_use(push, monkeypatch):
    a = push
    monkeypatch.setattr(service.settings, "push_vapid_private_key", "")
    assert not a["client"].get(a["base"] + "/preferences").json()["configured"]
    assert (
        a["client"]
        .post(a["base"] + "/subscriptions", json=a["device"], headers=a["csrf"])
        .status_code
        == 503
    )
    assert a["client"].get("/api/v1/auth/me").status_code == 200


def test_push_is_generic_and_delivery_is_durable(push, monkeypatch):
    a = push
    binding = register(a)
    notice(a)
    sent = []

    def fake(**kw):
        sent.append(kw)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(service, "webpush", fake)
    assert service.process_push(a["application"])["processed"] == 1
    assert json.loads(sent[0]["data"]) == {"type": "notification", "binding": binding}
    assert "Guest" not in sent[0]["data"] and "Sensitive" not in sent[0]["data"]
    assert service.process_push(a["application"])["processed"] == 0


def test_user_opt_out_suppresses_already_queued_delivery(push, monkeypatch):
    a = push
    register(a)
    notice(a)
    r = a["client"].patch(
        a["base"] + "/preferences",
        json={"enabled": False, "categories": service.CATEGORIES},
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    monkeypatch.setattr(
        service,
        "deliver",
        lambda sub: pytest.fail("opt-out must prevent network delivery"),
    )
    assert service.process_push(a["application"])["processed"] == 0


def test_category_preference_suppresses_delivery(push, monkeypatch):
    a = push
    register(a)
    notice(a)
    with a["owner"]() as db:
        db.get(PushPreference, (a["lodge"].id, a["user"].id)).categories = {
            **service.CATEGORIES,
            "task_assigned": False,
        }
        db.commit()
    monkeypatch.setattr(
        service, "deliver", lambda sub: pytest.fail("disabled category delivered")
    )
    assert service.process_push(a["application"])["processed"] == 0


@pytest.mark.parametrize("change", ["read", "session", "membership", "feature", "role"])
def test_delivery_rechecks_current_recipient_and_access(push, monkeypatch, change):
    a = push
    binding = register(a)
    nid = notice(a)
    with a["owner"]() as db:
        if change == "read":
            db.scalar(
                select(NotificationRecipient).where(
                    NotificationRecipient.notification_id == nid
                )
            ).read_at = datetime.now(timezone.utc)
        elif change == "session":
            db.get(
                AuthSession, db.get(PushSubscription, binding).session_id
            ).revoked_at = datetime.now(timezone.utc)
        elif change == "membership":
            db.scalar(
                select(Membership).where(
                    Membership.user_id == a["user"].id,
                    Membership.lodge_id == a["lodge"].id,
                )
            ).is_active = False
        elif change == "feature":
            db.add(
                LodgeEntitlementOverride(
                    lodge_id=a["lodge"].id, feature_key="tasks", enabled=False
                )
            )
        else:
            db.scalar(
                select(Membership).where(
                    Membership.user_id == a["user"].id,
                    Membership.lodge_id == a["lodge"].id,
                )
            ).role_id = db.scalar(select(Role.id).where(Role.key == "housekeeping"))
        db.commit()
    monkeypatch.setattr(
        service, "deliver", lambda sub: pytest.fail("revoked authority delivered")
    )
    assert service.process_push(a["application"])["processed"] == 0


def test_expired_subscription_can_still_disable_own_device(push):
    a = push
    binding = register(a)
    with a["owner"]() as db:
        db.get(Subscription, a["lodge"].id).expiry_date = date.today() - timedelta(
            days=1
        )
        db.commit()
    r = a["client"].request(
        "DELETE",
        "/api/v1/auth/push/subscriptions",
        json={"id": binding, "lodge_id": str(a["lodge"].id)},
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    with a["owner"]() as db:
        assert db.get(PushSubscription, binding) is None


def test_logout_removes_session_bindings(push):
    a = push
    binding = register(a)
    assert a["client"].post("/api/v1/auth/logout", headers=a["csrf"]).status_code == 200
    with a["owner"]() as db:
        assert db.get(PushSubscription, binding) is None


def test_gone_endpoint_is_removed_without_retries(push, monkeypatch):
    a = push
    binding = register(a)
    notice(a)
    monkeypatch.setattr(
        service, "deliver", lambda sub: SimpleNamespace(status_code=410)
    )
    service.process_push(a["application"])
    with a["owner"]() as db:
        assert db.get(PushSubscription, binding) is None


def test_network_failures_keep_jobs_without_secret_errors(push, monkeypatch):
    a = push
    register(a)
    notice(a)

    def fail(sub):
        raise RuntimeError("secret endpoint token must not appear in logs")

    monkeypatch.setattr(service, "deliver", fail)
    service.process_push(a["application"])
    with a["owner"]() as db:
        row = db.scalar(
            select(PushDelivery).where(
                PushDelivery.lodge_id == a["lodge"].id,
                PushDelivery.subscription_id.is_not(None),
            )
        )
        assert row.status == "failed" and row.last_error_code == "push_unavailable"


def test_subscription_rows_are_owner_scoped(push):
    a = push
    register(a)
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(uuid4()))
        assert db.scalar(select(PushSubscription.id)) is None
        assert db.scalar(select(PushPreference.user_id)) is None


def test_notification_creator_can_enqueue_but_cannot_read_other_devices(push):
    a = push
    with a["owner"]() as db:
        other = User(
            email=uuid4().hex + "@example.test",
            full_name="Other recipient",
            password_hash="unused",
        )
        db.add(other)
        db.flush()
        role = db.scalar(select(Role).where(Role.key == "lodge_admin"))
        db.add(Membership(lodge_id=a["lodge"].id, user_id=other.id, role_id=role.id))
        db.commit()
    nid = notice(a, other.id)
    with a["owner"]() as db:
        assert db.scalar(
            select(PushDelivery.id).where(
                PushDelivery.notification_id == nid, PushDelivery.user_id == other.id
            )
        )
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        assert (
            db.scalar(
                select(PushDelivery.id).where(PushDelivery.notification_id == nid)
            )
            is None
        )


def test_redirects_are_disabled_for_push_transport(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        service.requests.Session,
        "request",
        lambda self, *args, **kwargs: seen.update(kwargs),
    )
    service.NoRedirectSession().request(
        "POST", "https://fcm.googleapis.com/a", allow_redirects=True
    )
    assert seen["allow_redirects"] is False


def test_new_login_revokes_the_previous_browser_session(push):
    from app.security import token_hash

    a = push
    before = a["client"].cookies["lodge_session"]
    response = a["client"].post(
        "/api/v1/auth/login", json={"email": a["user"].email, "password": a["password"]}
    )
    assert response.status_code == 200, response.text
    assert a["client"].cookies["lodge_session"] != before
    with a["owner"]() as db:
        old = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash(before))
        )
        assert old.revoked_at is not None


def test_expired_session_capabilities_are_purged_even_without_pending_notices(push):
    a = push
    binding = register(a)
    with a["owner"]() as db:
        db.get(AuthSession, db.get(PushSubscription, binding).session_id).expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        db.commit()
    service.process_push(a["application"])
    with a["owner"]() as db:
        assert db.get(PushSubscription, binding) is None
