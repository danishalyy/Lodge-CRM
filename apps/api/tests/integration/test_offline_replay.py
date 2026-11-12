"""Real PostgreSQL replay: scope, conflicts, atomic receipts and existing workflows."""

from datetime import datetime, timedelta, timezone, date
from uuid import uuid4
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError
from app.models import (
    Task,
    TaskChecklistItem,
    TaskHistory,
    OfflineReceipt,
    Lodge,
    Membership,
    Role,
    StaffProfile,
    Unit,
    HousekeepingJob,
    Guest,
    Transfer,
    LodgeEntitlementOverride,
    Subscription,
    WildlifeSighting,
    WildlifeMedia,
)
from app.db import set_rls_context


@pytest.fixture
def work(account):
    a = account
    with a["owner"]() as db:
        staff = StaffProfile(
            lodge_id=a["lodge"].id, user_id=a["user"].id, full_name="Assigned staff"
        )
        unit = Unit(lodge_id=a["lodge"].id, name="Test room")
        guest = Guest(lodge_id=a["lodge"].id, first_name="Fixture", last_name="Guest")
        db.add_all([staff, unit, guest])
        db.flush()
        task = Task(
            lodge_id=a["lodge"].id,
            title="Check pump",
            created_by_user_id=a["user"].id,
            assigned_staff_id=staff.id,
            status="assigned",
        )
        hk = HousekeepingJob(
            lodge_id=a["lodge"].id,
            unit_id=unit.id,
            assigned_staff_id=staff.id,
            created_by_user_id=a["user"].id,
        )
        now = datetime.now(timezone.utc)
        transfer = Transfer(
            lodge_id=a["lodge"].id,
            guest_id=guest.id,
            transfer_type="pickup",
            scheduled_at=now + timedelta(hours=1),
            expected_end_at=now + timedelta(hours=2),
            pickup_location="Airport",
            dropoff_location="Lodge",
            created_by_user_id=a["user"].id,
        )
        db.add_all([task, hk, transfer])
        db.commit()
    a.update(
        task=task,
        hk=hk,
        transfer=transfer,
        staff=staff,
        base=f"/api/v1/lodges/{a['lodge'].id}/offline-actions",
    )
    return a


def action(
    a, kind="task.status", record=None, expected="assigned", value="accepted", **kw
):
    return {
        "id": str(uuid4()),
        "kind": kind,
        "record_id": str(record or a["task"].id),
        "expected": expected,
        "value": value,
        **kw,
    }


def post(a, body, headers=None):
    return a["client"].post(
        a["base"], json=body, headers=a["csrf"] if headers is None else headers
    )


def test_atomic_receipt_and_duplicate_does_not_repeat_history(work):
    a = work
    body = action(a)
    first = post(a, body)
    assert first.status_code == 200, first.text
    second = post(a, body)
    assert second.json()["duplicate"] is True
    with a["owner"]() as db:
        assert db.get(Task, a["task"].id).status == "accepted"
        assert (
            db.scalar(
                select(func.count())
                .select_from(OfflineReceipt)
                .where(OfflineReceipt.id == body["id"])
            )
            == 1
        )
        count = db.scalar(
            select(func.count())
            .select_from(TaskHistory)
            .where(
                TaskHistory.task_id == a["task"].id,
                TaskHistory.kind == "updated",
            )
        )
        assert count == 1
    assert post(a, {**body, "value": "started"}).status_code == 409


def test_stale_change_is_rejected_without_a_receipt(work):
    a = work
    body = action(a, expected="created")
    assert post(a, body).status_code == 409
    with a["owner"]() as db:
        assert db.get(OfflineReceipt, (body["id"], a["lodge"].id, a["user"].id)) is None


def test_failed_transition_rolls_back_receipt_and_existing_state(work):
    a = work
    body = action(a, value="completed")
    assert post(a, body).status_code in (409, 422)
    with a["owner"]() as db:
        assert db.get(OfflineReceipt, (body["id"], a["lodge"].id, a["user"].id)) is None
        assert db.get(Task, a["task"].id).status == "assigned"


def test_checklist_then_status_replays_serially(work):
    a = work
    with a["owner"]() as db:
        item = TaskChecklistItem(
            lodge_id=a["lodge"].id, task_id=a["task"].id, label="Check water"
        )
        db.add(item)
        db.commit()
    body = action(
        a, kind="task.checklist", expected=False, value=True, item_id=str(item.id)
    )
    assert post(a, body).status_code == 200
    assert post(a, body).json()["duplicate"] is True
    with a["owner"]() as db:
        assert db.get(TaskChecklistItem, item.id).completed_at is not None


def test_housekeeping_and_transfer_reuse_authoritative_transitions(work):
    a = work
    for body in [
        action(a, "housekeeping.status", a["hk"].id),
        action(
            a,
            "transfer.status",
            a["transfer"].id,
            expected="scheduled",
            value="confirmed",
        ),
    ]:
        r = post(a, body)
        assert r.status_code == 200, r.text
        assert post(a, body).json()["duplicate"]


def test_offline_entitlement_and_expiry_are_checked_on_replay(work):
    a = work
    with a["owner"]() as db:
        override = LodgeEntitlementOverride(
            lodge_id=a["lodge"].id, feature_key="offline_mobile", enabled=False
        )
        db.add(override)
        db.commit()
    assert post(a, action(a)).status_code == 403
    with a["owner"]() as db:
        db.delete(db.get(LodgeEntitlementOverride, (a["lodge"].id, "offline_mobile")))
        db.get(Subscription, a["lodge"].id).expiry_date = date.today() - timedelta(
            days=1
        )
        db.commit()
    assert post(a, action(a)).status_code == 403


def test_foreign_record_and_foreign_lodge_are_rejected(work):
    a = work
    with a["owner"]() as db:
        other = Lodge(name="Other offline " + uuid4().hex)
        db.add(other)
        db.flush()
        task = Task(
            lodge_id=other.id, title="Other task", created_by_user_id=a["user"].id
        )
        db.add(task)
        db.commit()
    assert post(a, action(a, record=task.id)).status_code == 404
    r = a["client"].post(
        f"/api/v1/lodges/{other.id}/offline-actions", headers=a["csrf"], json=action(a)
    )
    assert r.status_code == 403


def test_owned_role_cannot_replay_another_staff_task(work):
    a = work
    with a["owner"]() as db:
        member = db.scalar(
            select(Membership).where(
                Membership.user_id == a["user"].id, Membership.lodge_id == a["lodge"].id
            )
        )
        member.role_id = db.scalar(select(Role.id).where(Role.key == "housekeeping"))
        other = Task(
            lodge_id=a["lodge"].id,
            title="Unassigned",
            created_by_user_id=a["user"].id,
            status="assigned",
        )
        db.add(other)
        db.commit()
    assert post(a, action(a, record=other.id)).status_code == 403
    assert post(a, action(a)).status_code == 200


def test_replay_needs_csrf_and_expected_user_match(work):
    a = work
    assert post(a, action(a), headers={}).status_code == 403
    assert (
        post(
            a, action(a), headers={**a["csrf"], "X-Expected-User-Id": str(uuid4())}
        ).status_code
        == 409
    )


def test_receipts_are_user_and_tenant_scoped_append_only(work):
    a = work
    body = action(a)
    assert post(a, body).status_code == 200
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(uuid4()))
        assert db.scalar(select(OfflineReceipt.id)) is None
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM offline_receipts"))
        db.rollback()


def test_sighting_replay_keeps_client_reference_idempotency(work):
    a = work
    body = {
        "client_ref": str(uuid4()),
        "species": "Elephant",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    url = a["base"].replace("offline-actions", "offline-sightings")
    one = a["client"].post(url, json=body, headers=a["csrf"])
    assert one.status_code == 200, one.text
    two = a["client"].post(url, json=body, headers=a["csrf"])
    assert two.json()["id"] == one.json()["id"] and two.json()["duplicate"]


def test_photo_registration_acknowledgement_can_be_retried(work):
    a = work
    with a["owner"]() as db:
        sighting = WildlifeSighting(
            lodge_id=a["lodge"].id,
            client_ref=uuid4(),
            species="Elephant",
            observed_at=datetime.now(timezone.utc),
        )
        db.add(sighting)
        db.flush()
        media = WildlifeMedia(
            lodge_id=a["lodge"].id,
            sighting_id=sighting.id,
            object_key=f"lodges/{a['lodge'].id}/wildlife/known.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            sha256="a" * 64,
            uploaded_by_user_id=a["user"].id,
        )
        db.add(media)
        db.commit()
    body = {
        "sighting_id": str(sighting.id),
        "object_key": media.object_key,
        "content_type": "image/jpeg",
        "size_bytes": 100,
        "sha256": "a" * 64,
    }
    url = f"/api/v1/lodges/{a['lodge'].id}/wildlife/media"
    response = a["client"].post(url, json=body, headers=a["csrf"])
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(media.id)
    assert (
        a["client"]
        .post(url, json={**body, "sha256": "b" * 64}, headers=a["csrf"])
        .status_code
        == 409
    )


def test_unknown_target_status_is_a_validation_error(work):
    a = work
    assert post(a, action(a, value="not-a-status")).status_code == 422


def test_inspector_lost_acknowledgement_does_not_repeat_inspection(work):
    a = work
    with a["owner"]() as db:
        other = StaffProfile(lodge_id=a["lodge"].id, full_name="Other cleaner")
        db.add(other)
        db.flush()
        hk = db.get(HousekeepingJob, a["hk"].id)
        hk.assigned_staff_id = other.id
        hk.inspector_staff_id = a["staff"].id
        hk.status = "awaiting_inspection"
        member = db.scalar(
            select(Membership).where(
                Membership.user_id == a["user"].id, Membership.lodge_id == a["lodge"].id
            )
        )
        member.role_id = db.scalar(select(Role.id).where(Role.key == "housekeeping"))
        db.commit()
    body = action(
        a,
        "housekeeping.status",
        a["hk"].id,
        expected="awaiting_inspection",
        value="completed",
    )
    first = post(a, body)
    assert first.status_code == 200, first.text
    assert post(a, body).json()["duplicate"] is True


def test_disabled_housekeeping_is_gated_on_existing_read_and_write_routes(work):
    a = work
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id, feature_key="housekeeping", enabled=False
            )
        )
        db.commit()
    base = f"/api/v1/lodges/{a['lodge'].id}/housekeeping-jobs"
    assert a["client"].get(base).status_code == 403
    assert (
        a["client"]
        .patch(
            base + "/" + str(a["hk"].id), json={"status": "accepted"}, headers=a["csrf"]
        )
        .status_code
        == 403
    )
    assert (
        a["client"]
        .post(base, json={"unit_id": str(a["hk"].unit_id)}, headers=a["csrf"])
        .status_code
        == 403
    )
