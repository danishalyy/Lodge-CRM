"""Confirmed operational actions use real CRM mutations and existing tenant/role guards."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from app.models import (
    Guest,
    Unit,
    Stay,
    GuestRequest,
    Activity,
    Transfer,
    AIAction,
    AIMessage,
    AuditLog,
    OperationalEvent,
    Membership,
    Role,
    Permission,
    RolePermission,
    Lodge,
    LodgeEntitlementOverride,
)
from app.ai.providers.base import Completion, ToolCall
from test_ai_actions import acting, propose, reviewed
from test_ai_foundation import ai, create


@pytest.fixture
def operations(acting):
    a = acting
    with a["owner"]() as db:
        guest = Guest(
            lodge_id=a["lodge"].id,
            first_name="Existing",
            last_name="Guest",
            email="private@example.com",
            phone="+27820000001",
            allergies="PRIVATE_MEDICAL",
        )
        room = Unit(lodge_id=a["lodge"].id, name="River suite", unit_type="Suite")
        db.add_all([guest, room])
        db.commit()
    return {**a, "guest": guest, "room": room}


def details(a, kind):
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=30)
    common = {"guest_id": str(a["guest"].id)}
    return {
        "guest": {
            "first_name": "New",
            "last_name": "Visitor",
            "nationality": "South Africa",
            "phone": "+27821112222",
        },
        "stay": {
            **common,
            "unit_id": str(a["room"].id),
            "arrival_date": start.date().isoformat(),
            "departure_date": (start.date() + timedelta(days=2)).isoformat(),
            "party_size": 2,
        },
        "request": {
            **common,
            "request_type": "amenity",
            "description": "Please provide extra towels",
        },
        "activity": {
            "title": "Morning walk",
            "activity_type": "walk",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "guest_ids": [str(a["guest"].id)],
            "requires_vehicle": False,
        },
        "transfer": {
            **common,
            "transfer_type": "pickup",
            "scheduled_at": start.isoformat(),
            "expected_end_at": (start + timedelta(hours=1)).isoformat(),
            "pickup_location": "Airport",
            "dropoff_location": "Lodge",
        },
    }[kind]


MODELS = {
    "guest": Guest,
    "stay": Stay,
    "request": GuestRequest,
    "activity": Activity,
    "transfer": Transfer,
}


@pytest.mark.parametrize("kind", list(MODELS))
def test_new_actions_are_dry_until_confirmation_and_apply_exactly_once(
    operations, kind
):
    a = operations
    model = MODELS[kind]
    with a["owner"]() as db:
        before = db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.lodge_id == a["lodge"].id)
        )
        events = db.scalar(
            select(func.count())
            .select_from(OperationalEvent)
            .where(OperationalEvent.lodge_id == a["lodge"].id)
        )
    cid, response = propose(a, "propose_create_" + kind, details(a, kind))
    root, token, aid = reviewed(a, cid, response)
    assert response.json()["actions"][0]["action"] == "create_" + kind
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.lodge_id == a["lodge"].id)
            )
            == before
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationalEvent)
                .where(OperationalEvent.lodge_id == a["lodge"].id)
            )
            == events
        )
    applied = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "confirmed"
    assert (
        a["client"]
        .post(root + "/confirm", json={"token": token}, headers=a["csrf"])
        .json()
        == applied.json()
    )
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.lodge_id == a["lodge"].id)
            )
            == before + 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationalEvent)
                .where(OperationalEvent.lodge_id == a["lodge"].id)
            )
            == events + 1
        )
        if kind == "guest":
            row = db.get(AIAction, aid)
            assert row.payload == {} and "New" not in json.dumps(row.preview)
            assert set(row.result) == {"id"}


def test_selected_guest_action_uses_server_contact_reference_not_raw_email(
    operations, monkeypatch
):
    a = operations
    calls = []
    cid = create(a)

    def complete(messages, tools):
        calls.append((messages, tools))
        assert "traveller@example.com" not in json.dumps(messages)
        if len(calls) == 1:
            assert any(t["function"]["name"] == "select_action" for t in tools)
            return Completion(
                tool_calls=[
                    ToolCall(
                        "choose", "select_action", {"action": "propose_create_guest"}
                    )
                ]
            )
        names = {t["function"]["name"] for t in tools}
        assert (
            "propose_create_guest" in names and "propose_create_transfer" not in names
        )
        ref = re.search(
            r"guest_email_[a-f0-9]{16}",
            json.dumps(messages),
        ).group()
        return Completion(
            tool_calls=[
                ToolCall(
                    "guest",
                    "propose_create_guest",
                    {"first_name": "Thandi", "last_name": "Nkosi", "email": ref},
                )
            ]
        )

    monkeypatch.setattr(a["provider"], "complete", complete)
    response = a["client"].post(
        a["base"] + f"/conversations/{cid}/messages",
        json={
            "request_id": str(uuid4()),
            "content": "Add guest Thandi Nkosi, email traveller@example.com",
        },
        headers=a["csrf"],
    )
    root, token, aid = reviewed(a, cid, response)
    assert (
        next(
            f["value"]
            for f in response.json()["actions"][0]["preview"]["fields"]
            if f["key"] == "email"
        )
        == "traveller@example.com"
    )
    with a["owner"]() as db:
        assert all(
            "traveller@example.com" not in row.content
            for row in db.scalars(
                select(AIMessage).where(AIMessage.conversation_id == cid)
            )
        )
        assert not db.scalar(
            select(Guest.id).where(Guest.email == "traveller@example.com")
        )
    applied = a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    )
    assert applied.status_code == 200, applied.text
    with a["owner"]() as db:
        assert (
            db.get(Guest, applied.json()["result"]["id"]).email
            == "traveller@example.com"
        )
        assert "traveller@example.com" not in json.dumps(db.get(AIAction, aid).result)


@pytest.mark.parametrize(
    "email",
    ["invented@example.com", "guest_email_0000000000000000", "[email redacted]"],
)
def test_guest_email_cannot_be_invented_or_replayed(operations, email):
    a = operations
    _, response = propose(
        a,
        "propose_create_guest",
        {"first_name": "Fake", "last_name": "Address", "email": email},
    )
    assert response.status_code == 422, response.text
    with a["owner"]() as db:
        assert not db.scalar(select(Guest.id).where(Guest.first_name == "Fake"))
        assert not db.scalar(
            select(AIAction.id).where(AIAction.lodge_id == a["lodge"].id)
        )


@pytest.mark.parametrize("kind", list(MODELS))
def test_each_new_action_requires_its_own_role_permission(operations, kind):
    a = operations
    with a["owner"]() as db:
        role = Role(key="only_ai_" + uuid4().hex, name="AI without operations")
        db.add(role)
        db.flush()
        for key in ["ai.use", "ai.actions"]:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=db.scalar(
                        select(Permission.id).where(Permission.key == key)
                    ),
                )
            )
        db.scalar(
            select(Membership).where(Membership.user_id == a["user"].id)
        ).role_id = role.id
        db.commit()
    assert not any(
        t["name"].startswith("propose_")
        for t in a["client"].get(a["base"] + "/status").json()["tools"]
    )
    _, response = propose(a, "propose_create_" + kind, details(a, kind))
    assert response.status_code == 403, response.text


def test_guest_only_role_exposes_only_guest_creation(operations):
    a = operations
    with a["owner"]() as db:
        role = Role(key="guest_ai_" + uuid4().hex, name="Guest AI creator")
        db.add(role)
        db.flush()
        for key in ["ai.use", "ai.actions", "guests.manage"]:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=db.scalar(
                        select(Permission.id).where(Permission.key == key)
                    ),
                )
            )
        db.scalar(
            select(Membership).where(Membership.user_id == a["user"].id)
        ).role_id = role.id
        db.commit()
    assert [
        t["name"] for t in a["client"].get(a["base"] + "/status").json()["tools"]
    ] == ["propose_create_guest"]
    _, response = propose(a, "propose_create_guest", details(a, "guest"))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("kind", ["stay", "request", "activity", "transfer"])
def test_new_actions_reject_foreign_or_anonymised_guests(operations, kind):
    a = operations
    with a["owner"]() as db:
        other = Lodge(name="Other property " + uuid4().hex)
        db.add(other)
        db.flush()
        guest = Guest(lodge_id=other.id, first_name="Foreign", last_name="Private")
        db.add(guest)
        db.commit()
    values = details(a, kind)
    if kind == "activity":
        values["guest_ids"] = [str(guest.id)]
    else:
        values["guest_id"] = str(guest.id)
    _, response = propose(a, "propose_create_" + kind, values)
    assert response.status_code in [403, 404], response.text
    with a["owner"]() as db:
        db.get(Guest, a["guest"].id).anonymized_at = datetime.now(timezone.utc)
        db.commit()
    _, response = propose(a, "propose_create_" + kind, details(a, kind))
    assert response.status_code == 409, response.text


def test_stay_confirmation_rechecks_room_conflict(operations):
    a = operations
    values = details(a, "stay")
    cid, response = propose(a, "propose_create_stay", values)
    root, token, _ = reviewed(a, cid, response)
    reply = a["client"].post(
        f"/api/v1/lodges/{a['lodge'].id}/stays", json=values, headers=a["csrf"]
    )
    assert reply.status_code == 200, reply.text
    assert (
        a["client"]
        .post(root + "/confirm", json={"token": token}, headers=a["csrf"])
        .status_code
        == 409
    )
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Stay)
                .where(Stay.lodge_id == a["lodge"].id)
            )
            == 1
        )


def test_guest_duplicate_created_after_review_is_rejected(operations, monkeypatch):
    a = operations
    from app.ai import actions

    monkeypatch.setattr(
        actions,
        "contact_input",
        lambda content, enabled: (
            "Add visitor guest_email_test",
            {"guest_email_test": "duplicate@example.com"},
        ),
    )
    values = {
        "first_name": "Duplicate",
        "last_name": "Visitor",
        "email": "guest_email_test",
    }
    cid, response = propose(a, "propose_create_guest", values)
    root, token, _ = reviewed(a, cid, response)
    assert (
        a["client"]
        .post(
            f"/api/v1/lodges/{a['lodge'].id}/guests",
            json={**values, "email": "duplicate@example.com"},
            headers=a["csrf"],
        )
        .status_code
        == 200
    )
    assert (
        a["client"]
        .post(root + "/confirm", json={"token": token}, headers=a["csrf"])
        .status_code
        == 409
    )


@pytest.mark.parametrize("kind", ["activity", "transfer"])
def test_scheduling_requires_explicit_timezone(operations, kind):
    a = operations
    values = details(a, kind)
    key = "starts_at" if kind == "activity" else "scheduled_at"
    values[key] = datetime.fromisoformat(values[key]).replace(tzinfo=None).isoformat()
    # Both ends naive so the schema cannot fail for a different comparison error.
    end = "ends_at" if kind == "activity" else "expected_end_at"
    values[end] = datetime.fromisoformat(values[end]).replace(tzinfo=None).isoformat()
    _, response = propose(a, "propose_create_" + kind, values)
    assert response.status_code == 422, response.text


def test_guest_directory_never_exposes_contacts_or_health(operations):
    a = operations
    cid = create(a)
    a["provider"].replies = [
        Completion(
            tool_calls=[ToolCall("find", "get_guest_directory", {"search": "Existing"})]
        ),
        Completion("Found the guest"),
    ]
    response = a["client"].post(
        a["base"] + f"/conversations/{cid}/messages",
        json={"request_id": str(uuid4()), "content": "Find Existing Guest"},
        headers=a["csrf"],
    )
    assert response.status_code == 200, response.text
    context = json.dumps(a["provider"].calls)
    assert "Existing Guest" in context
    assert (
        "private@example.com" not in context
        and "PRIVATE_MEDICAL" not in context
        and "+27820000001" not in context
    )
    with a["owner"]() as db:
        db.get(Guest, a["guest"].id).anonymized_at = datetime.now(timezone.utc)
        db.commit()
    assert (
        a["client"].get(a["base"] + f"/conversations/{cid}/messages").status_code == 409
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "propose_create_user"},
        {"action": "propose_create_guest", "lodge_id": "other"},
        {"action": ["propose_create_guest"]},
    ],
)
def test_selector_cannot_expand_authority(operations, arguments):
    a = operations
    _, response = propose(a, "select_action", arguments)
    assert response.status_code in [403, 422], response.text
    with a["owner"]() as db:
        assert not db.scalar(
            select(AIAction.id).where(AIAction.lodge_id == a["lodge"].id)
        )


def test_guest_request_rejects_a_stay_belonging_to_someone_else(operations):
    a = operations
    with a["owner"]() as db:
        other = Guest(lodge_id=a["lodge"].id, first_name="Another", last_name="Guest")
        db.add(other)
        db.flush()
        start = date.today() + timedelta(days=40)
        stay = Stay(
            lodge_id=a["lodge"].id,
            guest_id=other.id,
            unit_id=a["room"].id,
            arrival_date=start,
            departure_date=start + timedelta(days=2),
        )
        db.add(stay)
        db.commit()
    values = {**details(a, "request"), "stay_id": str(stay.id)}
    _, response = propose(a, "propose_create_request", values)
    assert response.status_code == 409, response.text
    # The regular form and AI both use this same association check.
    response = a["client"].post(
        f"/api/v1/lodges/{a['lodge'].id}/requests", json=values, headers=a["csrf"]
    )
    assert response.status_code == 409, response.text


@pytest.mark.parametrize("kind", list(MODELS))
def test_each_new_action_is_hidden_and_denied_when_module_is_disabled(operations, kind):
    a = operations
    feature = {
        "guest": "guests",
        "stay": "stays",
        "request": "guest_requests",
        "activity": "activities",
        "transfer": "transfers",
    }[kind]
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key=feature,
                enabled=False,
                reason="Disabled test module",
            )
        )
        db.commit()
    assert "propose_create_" + kind not in {
        t["name"] for t in a["client"].get(a["base"] + "/status").json()["tools"]
    }
    _, response = propose(a, "propose_create_" + kind, details(a, kind))
    assert response.status_code == 403, response.text


def test_new_action_rechecks_permission_at_confirmation(operations):
    a = operations
    cid, response = propose(a, "propose_create_guest", details(a, "guest"))
    root, token, _ = reviewed(a, cid, response)
    with a["owner"]() as db:
        role = Role(
            key="lost_guest_" + uuid4().hex, name="AI reviewer without guest creation"
        )
        db.add(role)
        db.flush()
        for key in ["ai.use", "ai.actions"]:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=db.scalar(
                        select(Permission.id).where(Permission.key == key)
                    ),
                )
            )
        db.scalar(
            select(Membership).where(Membership.user_id == a["user"].id)
        ).role_id = role.id
        db.commit()
    assert a["client"].post(
        root + "/confirm", json={"token": token}, headers=a["csrf"]
    ).status_code in [403, 409]
    with a["owner"]() as db:
        assert not db.scalar(
            select(Guest.id).where(
                Guest.first_name == "New", Guest.lodge_id == a["lodge"].id
            )
        )
