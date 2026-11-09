from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from app.db import set_rls_context
from app.models import (
    Task,
    TaskHistory,
    StaffProfile,
    Department,
    Vehicle,
    MaintenanceTicket,
    Guest,
    GuestRequest,
    Role,
    Membership,
    Lodge,
    LodgeEntitlementOverride,
    Notification,
)


@pytest.fixture
def work(account):
    a = account
    with a["owner"]() as db:
        d = Department(lodge_id=a["lodge"].id, name="Operations")
        other = Department(lodge_id=a["lodge"].id, name="Other department")
        db.add_all([d, other])
        db.flush()
        one = StaffProfile(
            lodge_id=a["lodge"].id,
            full_name="Lerato Original",
            department_id=d.id,
            user_id=a["user"].id,
        )
        two = StaffProfile(
            lodge_id=a["lodge"].id, full_name="Sipho", department_id=d.id
        )
        v = Vehicle(
            lodge_id=a["lodge"].id, name="Cruiser 02", registration=uuid4().hex[:12]
        )
        db.add_all([one, two, v])
        db.flush()
        ticket = MaintenanceTicket(
            lodge_id=a["lodge"].id,
            title="Brake inspection",
            vehicle_id=v.id,
            department_id=d.id,
            created_by_user_id=a["user"].id,
        )
        db.add(ticket)
        db.commit()
    a.update(
        dep=d,
        other_dep=other,
        one=one,
        two=two,
        vehicle=v,
        ticket=ticket,
        base=f"/api/v1/lodges/{a['lodge'].id}/tasks",
    )
    return a


def create(a, **body):
    r = a["client"].post(
        a["base"], headers=a["csrf"], json={"title": "Inspect vehicle", **body}
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def patch(a, tid, **body):
    return a["client"].patch(a["base"] + "/" + tid, headers=a["csrf"], json=body)


def history(a, tid):
    r = a["client"].get(a["base"] + "/" + tid + "/history")
    assert r.status_code == 200, r.text
    return r.json()


def test_actual_assignment_and_immutable_reassignment_history(work):
    a = work
    tid = create(a, assigned_staff_id=str(a["one"].id))
    first = history(a, tid)
    assert (
        first["timing"]["assigned_at"]
        and first["items"][0]["after"]["assigned_staff_name"] == "Lerato Original"
    )
    assert (
        first["items"][0]["actor"] == "Security Test"
        and first["items"][0]["kind"] == "created"
    )
    for status in ["accepted", "started"]:
        assert patch(a, tid, status=status).status_code == 200
    assert patch(a, tid, assigned_staff_id=str(a["two"].id)).status_code == 200
    result = history(a, tid)
    last = result["items"][-1]
    assert (
        last["before"]["assigned_staff_name"] == "Lerato Original"
        and last["after"]["assigned_staff_name"] == "Sipho"
    )
    assert last["before"]["started_at"] and last["after"]["started_at"] is None
    assert result["timing"]["assigned_at"] != first["timing"]["assigned_at"]
    with a["owner"]() as db:
        db.get(StaffProfile, a["one"].id).full_name = "Renamed later"
        db.get(Department, a["dep"].id).name = "Renamed department"
        db.commit()
    old = history(a, tid)["items"][0]["after"]
    assert (
        old["assigned_staff_name"] == "Lerato Original"
        and old["department_name"] == "Operations"
    )
    before_count = len(history(a, tid)["items"])
    assert patch(a, tid, assigned_staff_id=str(a["two"].id)).status_code == 200
    assert len(history(a, tid)["items"]) == before_count


def test_assignment_requires_a_person_and_timestamps_are_not_client_controlled(work):
    a = work
    tid = create(a)
    assert history(a, tid)["timing"]["assigned_at"] is None
    assert patch(a, tid, status="assigned").status_code == 422
    assert patch(a, tid, assigned_at="2020-01-01T00:00:00Z").status_code == 422
    assert len(history(a, tid)["items"]) == 1


def test_links_are_validated_preserved_and_can_be_cleared(work):
    a = work
    tid = create(
        a, vehicle_id=str(a["vehicle"].id), maintenance_ticket_id=str(a["ticket"].id)
    )
    result = history(a, tid)
    assert (
        result["timing"]["vehicle_name"] == "Cruiser 02"
        and result["timing"]["maintenance_title"] == "Brake inspection"
    )
    assert patch(a, tid, vehicle_id=None, maintenance_ticket_id=None).status_code == 200
    last = history(a, tid)["items"][-1]
    assert (
        last["before"]["vehicle_id"] == str(a["vehicle"].id)
        and last["after"]["vehicle_id"] is None
    )
    with a["owner"]() as db:
        other = Vehicle(lodge_id=a["lodge"].id, registration=uuid4().hex[:12])
        db.add(other)
        db.commit()
    assert (
        a["client"]
        .post(
            a["base"],
            headers=a["csrf"],
            json={
                "title": "Mismatch",
                "vehicle_id": str(other.id),
                "maintenance_ticket_id": str(a["ticket"].id),
            },
        )
        .status_code
        == 409
    )


def test_link_visibility_rechecks_feature_grants(work):
    a = work
    tid = create(
        a, vehicle_id=str(a["vehicle"].id), maintenance_ticket_id=str(a["ticket"].id)
    )
    with a["owner"]() as db:
        for key in ["fleet", "maintenance"]:
            db.add(
                LodgeEntitlementOverride(
                    lodge_id=a["lodge"].id,
                    feature_key=key,
                    enabled=False,
                    reason="Test",
                )
            )
        db.commit()
    result = history(a, tid)
    assert (
        result["timing"]["vehicle_id"] is None
        and result["timing"]["maintenance_ticket_id"] is None
    )
    assert (
        "vehicle_id" not in result["items"][0]["after"]
        and "maintenance_ticket_id" not in result["items"][0]["after"]
    )
    assert (
        a["client"]
        .post(
            a["base"],
            headers=a["csrf"],
            json={"title": "Hidden link", "vehicle_id": str(a["vehicle"].id)},
        )
        .status_code
        == 403
    )


def test_foreign_links_and_history_are_blocked_by_tenant_and_composite_keys(work):
    a = work
    tid = create(a)
    with a["owner"]() as db:
        other = Lodge(name="Other lodge")
        db.add(other)
        db.flush()
        v = Vehicle(lodge_id=other.id, registration=uuid4().hex[:12])
        db.add(v)
        db.commit()
    assert (
        a["client"]
        .post(
            a["base"],
            headers=a["csrf"],
            json={"title": "Foreign link", "vehicle_id": str(v.id)},
        )
        .status_code
        == 404
    )
    assert (
        a["client"].get(f"/api/v1/lodges/{other.id}/tasks/{tid}/history").status_code
        == 403
    )
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        db.get(Task, __import__("uuid").UUID(tid)).vehicle_id = v.id
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        set_rls_context(db, str(other.id), False, str(a["user"].id))
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 0
        )


def test_history_is_database_generated_and_append_only(work):
    a = work
    tid = create(a)
    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        for statement in [
            "UPDATE task_history SET kind='fake' WHERE task_id=:id",
            "DELETE FROM task_history WHERE task_id=:id",
        ]:
            with pytest.raises(DBAPIError):
                db.execute(text(statement), {"id": tid})
            db.rollback()
            set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "INSERT INTO task_history(lodge_id,task_id,kind,changed_fields,\"after\",occurred_at) VALUES(:lodge,:id,'fake','[]','{}',now())"
                ),
                {"lodge": str(a["lodge"].id), "id": tid},
            )
        db.rollback()


def test_recurring_tasks_keep_links_timestamps_checklist_and_notifications(work):
    a = work
    tid = create(
        a,
        assigned_staff_id=str(a["one"].id),
        vehicle_id=str(a["vehicle"].id),
        maintenance_ticket_id=str(a["ticket"].id),
        recurrence_interval_days=7,
        due_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )
    for status in ["accepted", "started", "completed"]:
        assert patch(a, tid, status=status).status_code == 200
    assert patch(a, tid, status="completed").status_code == 200
    with a["owner"]() as db:
        tasks = db.scalars(select(Task).where(Task.lodge_id == a["lodge"].id)).all()
        assert len(tasks) == 2
        nxt = next(t for t in tasks if str(t.id) != tid)
        assert (
            nxt.assigned_at
            and nxt.vehicle_id == a["vehicle"].id
            and nxt.maintenance_ticket_id == a["ticket"].id
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == nxt.id)
            )
            == 1
        )
        assert db.scalar(
            select(Notification.id).where(
                Notification.resource_id == str(nxt.id),
                Notification.notification_type == "task.assigned",
            )
        )
    result = history(a, tid)
    assert (
        result["timing"]["completion_seconds"] >= 0
        and result["timing"]["overdue_seconds"] >= 3600
    )


def test_request_conversion_and_resolution_are_in_history(work):
    a = work
    with a["owner"]() as db:
        guest = Guest(lodge_id=a["lodge"].id, first_name="Guest", last_name="Fixture")
        db.add(guest)
        db.flush()
        req = GuestRequest(
            lodge_id=a["lodge"].id,
            guest_id=guest.id,
            request_type="amenity",
            description="Extra blanket",
            assigned_staff_id=a["one"].id,
            department_id=a["dep"].id,
            created_by_user_id=a["user"].id,
        )
        db.add(req)
        db.commit()
    base = f"/api/v1/lodges/{a['lodge'].id}/requests/{req.id}"
    r = a["client"].post(base + "/create-task", headers=a["csrf"])
    assert r.status_code == 200, r.text
    tid = r.json()["task_id"]
    assert a["client"].post(base + "/create-task", headers=a["csrf"]).status_code == 409
    assert history(a, tid)["timing"]["assigned_at"]
    for status in ["in_progress", "resolved"]:
        response = a["client"].patch(
            base,
            headers=a["csrf"],
            json={"status": status, "resolution": "Blanket delivered"},
        )
        assert response.status_code == 200, response.text
    last = history(a, tid)["items"][-1]
    assert last["after"]["status"] == "completed" and last["after"]["completed_at"]


def test_current_assignment_and_department_gate_history(work):
    a = work
    tid = create(a, assigned_staff_id=str(a["two"].id))
    with a["owner"]() as db:
        m = db.scalar(select(Membership).where(Membership.user_id == a["user"].id))
        m.role_id = db.scalar(select(Role.id).where(Role.key == "general_staff"))
        db.commit()
    assert a["client"].get(a["base"] + "/" + tid + "/history").status_code == 403
    with a["owner"]() as db:
        db.get(Task, __import__("uuid").UUID(tid)).assigned_staff_id = a["one"].id
        db.commit()
    assert a["client"].get(a["base"] + "/" + tid + "/history").status_code == 200
    assert patch(a, tid, vehicle_id=None).status_code == 403
    with a["owner"]() as db:
        m = db.scalar(select(Membership).where(Membership.user_id == a["user"].id))
        m.role_id = db.scalar(select(Role.id).where(Role.key == "department_manager"))
        m.department_id = a["other_dep"].id
        db.commit()
    assert a["client"].get(a["base"] + "/" + tid + "/history").status_code == 403


def test_failed_transition_rolls_back_history_and_metadata(work):
    a = work
    tid = create(a, assigned_staff_id=str(a["one"].id), proof_required=True)
    for status in ["accepted", "started"]:
        assert patch(a, tid, status=status).status_code == 200
    before = history(a, tid)
    assert patch(a, tid, status="completed").status_code == 409
    after = history(a, tid)
    assert after["items"] == before["items"] and after["timing"]["completed_at"] is None


def test_history_pagination_and_feature_gate(work):
    a = work
    tid = create(a)
    for priority in ["high", "normal", "critical"]:
        assert patch(a, tid, priority=priority).status_code == 200
    first = a["client"].get(a["base"] + "/" + tid + "/history?limit=2").json()
    second = a["client"].get(a["base"] + "/" + tid + "/history?limit=2&offset=2").json()
    assert first["has_more"] and not second["has_more"]
    assert len({x["id"] for x in first["items"] + second["items"]}) == 4
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key="tasks",
                enabled=False,
                reason="Test",
            )
        )
        db.commit()
    assert a["client"].get(a["base"] + "/" + tid + "/history").status_code == 403
    assert a["client"].get(a["base"]).status_code == 403
    assert (
        a["client"]
        .post(a["base"], headers=a["csrf"], json={"title": "Disabled task"})
        .status_code
        == 403
    )
    assert patch(a, tid, priority="normal").status_code == 403
    assert a["client"].get(a["base"] + "/" + tid + "/checklist").status_code == 403
    assert a["client"].get(a["base"] + "/" + tid + "/comments").status_code == 403


def second_manager(a):
    from app.models import User, AuthSession
    from app.security import token_hash
    from fastapi.testclient import TestClient
    from app.main import app

    raw = uuid4().hex + uuid4().hex
    csrf = uuid4().hex
    with a["owner"]() as db:
        user = User(
            email=uuid4().hex + "@example.com",
            full_name="Second manager",
            password_hash="disabled-concurrency-fixture",
        )
        db.add(user)
        db.flush()
        db.add(
            Membership(
                user_id=user.id,
                lodge_id=a["lodge"].id,
                role_id=db.scalar(select(Role.id).where(Role.key == "lodge_admin")),
            )
        )
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=token_hash(raw),
                csrf_hash=token_hash(csrf),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    client = TestClient(app)
    client.cookies.set("lodge_session", raw)
    client.cookies.set("lodge_csrf", csrf)
    return client, {"X-CSRF-Token": csrf}


def test_concurrent_completion_is_once_across_two_managers(work):
    from concurrent.futures import ThreadPoolExecutor

    a = work
    tid = create(
        a,
        assigned_staff_id=str(a["one"].id),
        recurrence_interval_days=7,
        due_at=datetime.now(timezone.utc).isoformat(),
    )
    for status in ["accepted", "started"]:
        assert patch(a, tid, status=status).status_code == 200
    other, csrf = second_manager(a)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [
                pool.submit(patch, a, tid, status="completed"),
                pool.submit(
                    other.patch,
                    a["base"] + "/" + tid,
                    headers=csrf,
                    json={"status": "completed"},
                ),
            ]
            results = [job.result(timeout=15) for job in jobs]
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    finally:
        other.close()
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 2
        )
    assert len(history(a, tid)["items"]) == 4


def test_concurrent_request_resolution_and_task_completion_share_lock_order(work):
    from concurrent.futures import ThreadPoolExecutor

    a = work
    tid = create(a, assigned_staff_id=str(a["one"].id))
    for status in ["accepted", "started"]:
        assert patch(a, tid, status=status).status_code == 200
    with a["owner"]() as db:
        guest = Guest(lodge_id=a["lodge"].id, first_name="Linked", last_name="Guest")
        db.add(guest)
        db.flush()
        req = GuestRequest(
            lodge_id=a["lodge"].id,
            guest_id=guest.id,
            task_id=__import__("uuid").UUID(tid),
            request_type="amenity",
            description="Linked work",
            status="in_progress",
            created_by_user_id=a["user"].id,
        )
        db.add(req)
        db.commit()
    other, csrf = second_manager(a)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [
                pool.submit(patch, a, tid, status="completed"),
                pool.submit(
                    other.patch,
                    f"/api/v1/lodges/{a['lodge'].id}/requests/{req.id}",
                    headers=csrf,
                    json={"status": "resolved", "resolution": "Delivered"},
                ),
            ]
            results = [job.result(timeout=15) for job in jobs]
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    finally:
        other.close()
    assert len(history(a, tid)["items"]) == 4


def test_inactive_staff_are_not_assigned_to_new_or_recurring_work(work):
    a = work
    tid = create(
        a,
        assigned_staff_id=str(a["one"].id),
        recurrence_interval_days=7,
        due_at=datetime.now(timezone.utc).isoformat(),
    )
    with a["owner"]() as db:
        db.get(StaffProfile, a["two"].id).employment_status = "inactive"
        db.commit()
    assert patch(a, tid, assigned_staff_id=str(a["two"].id)).status_code == 409
    for status in ["accepted", "started"]:
        assert patch(a, tid, status=status).status_code == 200
    with a["owner"]() as db:
        db.get(StaffProfile, a["one"].id).employment_status = "inactive"
        db.commit()
    # The manager remains active; unlink their staff fixture to exercise completion of work assigned to an inactive colleague.
    with a["owner"]() as db:
        db.get(StaffProfile, a["one"].id).user_id = None
        db.commit()
    assert patch(a, tid, status="completed").status_code == 200
    with a["owner"]() as db:
        nxt = db.scalar(
            select(Task).where(Task.lodge_id == a["lodge"].id, Task.id != tid)
        )
        assert (
            nxt
            and nxt.assigned_staff_id is None
            and nxt.assigned_at is None
            and nxt.status == "created"
        )


from test_ai_foundation import ai
from test_ai_actions import acting, propose, reviewed


def test_ai_review_shows_explicit_link_removal_and_dry_run_history_rolls_back(acting):
    a = acting
    with a["owner"]() as db:
        vehicle = Vehicle(lodge_id=a["lodge"].id, registration=uuid4().hex[:12])
        db.add(vehicle)
        db.flush()
        task = Task(
            lodge_id=a["lodge"].id,
            title="Linked work",
            vehicle_id=vehicle.id,
            created_by_user_id=a["user"].id,
        )
        db.add(task)
        db.commit()
        tid = task.id
    cid, response = propose(
        a, "propose_update_task", {"task_id": str(tid), "changes": {"vehicle_id": None}}
    )
    root, token, aid = reviewed(a, cid, response)
    field = next(
        f
        for f in response.json()["actions"][0]["preview"]["fields"]
        if f["key"] == "vehicle_id"
    )
    assert field["value"] is None and field["previous"] == str(vehicle.id)
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 1
        )
    r = a["client"].post(root + "/confirm", headers=a["csrf"], json={"token": token})
    assert r.status_code == 200, r.text
    with a["owner"]() as db:
        assert db.get(Task, tid).vehicle_id is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 2
        )


def test_deleted_task_retains_evidence_but_has_no_history_reader(work):
    from uuid import UUID

    a = work
    tid = create(a)
    with a["owner"]() as db:
        task = db.get(Task, UUID(tid))
        created_at = task.created_at
        db.delete(task)
        db.commit()
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 1
        )
    with a["owner"]() as db:
        saved = db.scalar(select(TaskHistory).where(TaskHistory.task_id == tid))
        assert datetime.fromisoformat(saved.after["created_at"]) == created_at
    assert a["client"].get(a["base"] + "/" + tid + "/history").status_code == 404


def test_maintenance_history_labels_follow_current_department_scope(work):
    a = work
    tid = create(
        a,
        assigned_staff_id=str(a["one"].id),
        vehicle_id=str(a["vehicle"].id),
        maintenance_ticket_id=str(a["ticket"].id),
    )
    with a["owner"]() as db:
        db.get(MaintenanceTicket, a["ticket"].id).department_id = a["other_dep"].id
        m = db.scalar(select(Membership).where(Membership.user_id == a["user"].id))
        m.role_id = db.scalar(select(Role.id).where(Role.key == "department_manager"))
        m.department_id = a["dep"].id
        db.commit()
    result = history(a, tid)
    assert (
        result["timing"]["maintenance_ticket_id"] is None
        and result["timing"]["maintenance_title"] is None
    )
    assert (
        "maintenance_ticket_id" not in result["items"][0]["after"]
        and "maintenance_title" not in result["items"][0]["after"]
    )
    assert patch(a, tid, maintenance_ticket_id=str(a["ticket"].id)).status_code == 403


def test_disabling_advanced_tasks_stops_recurrence_without_blocking_completion(work):
    a = work
    tid = create(
        a,
        assigned_staff_id=str(a["one"].id),
        recurrence_interval_days=7,
        due_at=datetime.now(timezone.utc).isoformat(),
    )
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key="advanced_tasks",
                enabled=False,
                reason="Test",
            )
        )
        db.commit()
    for status in ["accepted", "started", "completed"]:
        assert patch(a, tid, status=status).status_code == 200
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.lodge_id == a["lodge"].id)
            )
            == 1
        )


def test_reference_changes_while_waiting_for_lock_cannot_use_cached_staff(
    acting, monkeypatch
):
    from app import main
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor

    a = acting
    with a["owner"]() as db:
        staff = StaffProfile(lodge_id=a["lodge"].id, full_name="Target staff")
        task = Task(
            lodge_id=a["lodge"].id,
            title="Unassigned work",
            created_by_user_id=a["user"].id,
        )
        db.add_all([staff, task])
        db.commit()
        sid = staff.id
        tid = task.id
    cid, response = propose(
        a,
        "propose_update_task",
        {"task_id": str(tid), "changes": {"assigned_staff_id": str(sid)}},
    )
    root, token, aid = reviewed(a, cid, response)
    entered = Event()
    original = main._update_task_record

    def observed(*args, **kwargs):
        entered.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "_update_task_record", observed)
    with a["application"]() as blocker:
        set_rls_context(blocker, str(a["lodge"].id), False, str(a["user"].id))
        blocker.get(StaffProfile, sid).employment_status = "inactive"
        blocker.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                a["client"].post,
                root + "/confirm",
                headers=a["csrf"],
                json={"token": token},
            )
            try:
                assert entered.wait(
                    5
                ), "Confirmation did not reach the mutation boundary"
            finally:
                blocker.commit()
            result = future.result(timeout=10)
    assert result.status_code == 409, result.text
    with a["owner"]() as db:
        assert db.get(Task, tid).assigned_staff_id is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 1
        )


def test_normal_edit_refreshes_cached_own_staff_after_waiting_for_lock(
    work, monkeypatch
):
    from app import main
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    from uuid import UUID

    a = work
    tid = create(a, assigned_staff_id=str(a["two"].id))
    entered = Event()
    original = main.lock_task

    def observed(*args, **kwargs):
        entered.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "lock_task", observed)
    with a["application"]() as blocker:
        set_rls_context(blocker, str(a["lodge"].id), False, str(a["user"].id))
        blocker.get(StaffProfile, a["one"].id).employment_status = "inactive"
        blocker.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(patch, a, tid, assigned_staff_id=str(a["one"].id))
            try:
                assert entered.wait(5), "Edit did not reach the lock boundary"
            finally:
                blocker.commit()
            result = future.result(timeout=10)
    assert result.status_code == 409, result.text
    with a["owner"]() as db:
        assert db.get(Task, UUID(tid)).assigned_staff_id == a["two"].id
        assert (
            db.scalar(
                select(func.count())
                .select_from(TaskHistory)
                .where(TaskHistory.task_id == tid)
            )
            == 1
        )
