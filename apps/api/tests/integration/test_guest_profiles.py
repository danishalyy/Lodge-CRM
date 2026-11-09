from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.models import (
    Guest,
    GuestCommunication,
    Lodge,
    OperationalEvent,
    AuditLog,
    Membership,
    Role,
    Subscription,
    Unit,
    Stay,
    LodgeEntitlementOverride,
)
from app.db import set_rls_context


@pytest.fixture
def crm(account):
    a = account
    a["guests"] = f"/api/v1/lodges/{a['lodge'].id}/guests"
    r = a["client"].post(
        a["guests"],
        headers=a["csrf"],
        json={
            "first_name": "Maya",
            "last_name": "Laurent",
            "birthday": "1985-03-21",
            "anniversary": "2012-09-18",
            "repeat_guest": True,
            "safari_preferences": "Quiet birding drives",
        },
    )
    assert r.status_code == 200, r.text
    a["guest"] = r.json()
    a["base"] = a["guests"] + "/" + a["guest"]["id"]
    return a


def interaction(**extra):
    return {
        "client_reference": str(uuid4()),
        "channel": "phone",
        "direction": "inbound",
        "subject": "Arrival details",
        "message": "Guest confirmed the arrival time.",
        **extra,
    }


def test_guest_fields_persist_list_patch_clear_and_export(crm):
    a = crm
    g = next(
        g for g in a["client"].get(a["guests"]).json() if g["id"] == a["guest"]["id"]
    )
    assert (
        g["birthday"] == "1985-03-21"
        and g["anniversary"] == "2012-09-18"
        and g["repeat_guest"]
    )
    result = a["client"].patch(
        a["base"], headers=a["csrf"], json={"notes": "Updated note"}
    )
    assert result.status_code == 200 and result.json()["birthday"] == g["birthday"]
    result = a["client"].patch(
        a["base"],
        headers=a["csrf"],
        json={
            "birthday": None,
            "anniversary": None,
            "repeat_guest": False,
            "safari_preferences": "Morning drives",
        },
    )
    assert result.status_code == 200, result.text
    assert (
        result.json()["birthday"] is None
        and result.json()["anniversary"] is None
        and not result.json()["repeat_guest"]
    )
    data = a["client"].get(a["base"] + "/export").json()
    assert (
        data["guest"]["safari_preferences"] == "Morning drives"
        and data["communications"] == []
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("birthday", "not-a-date"),
        ("anniversary", "2100-01-01"),
        ("birthday", str(date.today() + timedelta(days=1))),
        ("repeat_guest", "unknown"),
        ("safari_preferences", "x" * 4001),
    ],
)
def test_invalid_guest_details_are_field_errors(crm, field, value):
    r = crm["client"].patch(crm["base"], headers=crm["csrf"], json={field: value})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"][-1] == field


def test_communication_log_has_exactly_once_retry_and_private_content(crm):
    a = crm
    payload = interaction()
    first = a["client"].post(
        a["base"] + "/communications", headers=a["csrf"], json=payload
    )
    assert first.status_code == 200, first.text
    second = a["client"].post(
        a["base"] + "/communications", headers=a["csrf"], json=payload
    )
    assert second.json()["id"] == first.json()["id"]
    changed = a["client"].post(
        a["base"] + "/communications",
        headers=a["csrf"],
        json={**payload, "message": "Different note"},
    )
    assert changed.status_code == 409
    listing = a["client"].get(a["base"] + "/communications").json()
    assert len(listing["items"]) == 1 and not listing["has_more"]
    assert listing["items"][0]["message"] == payload["message"]
    assert (
        a["client"].get(a["base"] + "/export").json()["communications"][0]["id"]
        == first.json()["id"]
    )
    with a["owner"]() as db:
        events = db.scalars(
            select(OperationalEvent).where(
                OperationalEvent.resource_id == a["guest"]["id"],
                OperationalEvent.event_type == "guest.communication_logged",
            )
        ).all()
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.resource_id == a["guest"]["id"],
                AuditLog.action == "guest.communication_logged",
            )
        ).all()
        assert len(events) == len(logs) == 1
        assert all(
            payload["message"] not in e.summary + e.detail
            and payload["subject"] not in e.summary + e.detail
            for e in events
        )


def test_communications_pagination_is_stable(crm):
    a = crm
    for day in range(3):
        r = a["client"].post(
            a["base"] + "/communications",
            headers=a["csrf"],
            json=interaction(occurred_at=f"2020-01-0{day+1}T10:00:00Z"),
        )
        assert r.status_code == 200, r.text
    first = a["client"].get(a["base"] + "/communications?limit=2").json()
    second = a["client"].get(a["base"] + "/communications?limit=2&offset=2").json()
    assert first["has_more"] and not second["has_more"] and len(second["items"]) == 1
    assert not set(x["id"] for x in first["items"]) & set(
        x["id"] for x in second["items"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"message": " "},
        {"subject": " "},
        {"channel": "sms"},
        {"direction": "sent"},
        {"occurred_at": "2020-01-01T10:00:00"},
        {"occurred_at": "2100-01-01T00:00:00Z"},
        {"user_id": str(uuid4())},
    ],
)
def test_invalid_interaction_is_rejected(crm, changes):
    r = crm["client"].post(
        crm["base"] + "/communications",
        headers=crm["csrf"],
        json=interaction(**changes),
    )
    assert r.status_code == 422, r.text


def test_log_requires_csrf_role_feature_and_writable_subscription(crm):
    a = crm
    url = a["base"] + "/communications"
    assert a["client"].post(url, json=interaction()).status_code == 403
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key="guests",
                enabled=False,
                reason="Test gate",
            )
        )
        db.commit()
    assert (
        a["client"].post(url, headers=a["csrf"], json=interaction()).status_code == 403
    )
    assert a["client"].get(url).status_code == 403
    with a["owner"]() as db:
        db.query(LodgeEntitlementOverride).filter_by(
            lodge_id=a["lodge"].id, feature_key="guests"
        ).delete()
        membership = db.scalar(
            select(Membership).where(
                Membership.lodge_id == a["lodge"].id, Membership.user_id == a["user"].id
            )
        )
        membership.role_id = db.scalar(select(Role.id).where(Role.key == "read_only"))
        db.commit()
    assert a["client"].get(url).status_code == 200
    assert (
        a["client"].post(url, headers=a["csrf"], json=interaction()).status_code == 403
    )
    with a["owner"]() as db:
        membership = db.scalar(
            select(Membership).where(
                Membership.lodge_id == a["lodge"].id, Membership.user_id == a["user"].id
            )
        )
        membership.role_id = db.scalar(select(Role.id).where(Role.key == "lodge_admin"))
        sub = db.scalar(
            select(Subscription).where(Subscription.lodge_id == a["lodge"].id)
        )
        sub.expiry_date = date.today() - timedelta(days=1)
        db.commit()
    assert (
        a["client"].post(url, headers=a["csrf"], json=interaction()).status_code == 403
    )


def test_guest_communication_foreign_ids_and_force_rls(crm):
    a = crm
    with a["owner"]() as db:
        other = Lodge(name="Other property")
        db.add(other)
        db.flush()
        foreign = Guest(lodge_id=other.id, first_name="Other", last_name="Guest")
        db.add(foreign)
        db.commit()
    assert (
        a["client"]
        .get(a["guests"] + "/" + str(foreign.id) + "/communications")
        .status_code
        == 404
    )
    assert (
        a["client"]
        .post(
            a["guests"] + "/" + str(foreign.id) + "/communications",
            headers=a["csrf"],
            json=interaction(),
        )
        .status_code
        == 404
    )
    a["client"].post(
        a["base"] + "/communications", headers=a["csrf"], json=interaction()
    )
    with a["application"]() as db:
        set_rls_context(db, str(other.id), False, str(a["user"].id))
        assert (
            db.scalar(
                select(func.count())
                .select_from(GuestCommunication)
                .where(GuestCommunication.guest_id == a["guest"]["id"])
            )
            == 0
        )
        # Composite key rejects a same-tenant note referencing a foreign guest even if RLS permits its lodge_id.
        db.add(
            GuestCommunication(
                lodge_id=other.id,
                guest_id=a["guest"]["id"],
                client_reference=uuid4(),
                created_by_user_id=a["user"].id,
                channel="phone",
                direction="inbound",
                subject="Invalid",
                message="Invalid",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_anonymisation_clears_new_data_and_preserves_redacted_history(crm):
    a = crm
    assert (
        a["client"]
        .post(a["base"] + "/communications", headers=a["csrf"], json=interaction())
        .status_code
        == 200
    )
    response = a["client"].post(a["base"] + "/anonymize", headers=a["csrf"])
    assert response.status_code == 200, response.text
    data = a["client"].get(a["base"] + "/export").json()
    assert data["guest"]["birthday"] is None and data["guest"]["anniversary"] is None
    assert (
        not data["guest"]["repeat_guest"]
        and data["guest"]["safari_preferences"] == ""
        and data["guest"]["anonymized_at"]
    )
    assert len(data["communications"]) == 1 and data["communications"][0]["redacted_at"]
    assert (
        data["communications"][0]["subject"]
        == data["communications"][0]["message"]
        == ""
    )
    assert (
        a["client"]
        .post(a["base"] + "/communications", headers=a["csrf"], json=interaction())
        .status_code
        == 409
    )
    assert (
        a["client"]
        .patch(a["base"], headers=a["csrf"], json={"birthday": "1980-01-01"})
        .status_code
        == 409
    )


def test_anonymisation_active_stay_keeps_new_data(crm):
    a = crm
    with a["owner"]() as db:
        room = Unit(lodge_id=a["lodge"].id, name="Guest test unit")
        db.add(room)
        db.flush()
        db.add(
            Stay(
                lodge_id=a["lodge"].id,
                unit_id=room.id,
                guest_id=a["guest"]["id"],
                arrival_date=date.today(),
                departure_date=date.today() + timedelta(days=2),
                status="in_house",
            )
        )
        db.commit()
    assert (
        a["client"].post(a["base"] + "/anonymize", headers=a["csrf"]).status_code == 409
    )
    assert (
        a["client"].get(a["base"] + "/export").json()["guest"]["birthday"]
        == "1985-03-21"
    )
