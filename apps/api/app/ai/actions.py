"""Proposals are data, never executable model instructions. Only explicit app confirmation writes."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, func, text
from ..config import settings
from ..models import (
    AIAction,
    Task,
    Unit,
    StaffProfile,
    Department,
    Guest,
    Vehicle,
    MaintenanceAsset,
    MaintenanceTicket,
    GuestRequest,
    Stay,
)
from ..schemas import (
    TaskCreate,
    TaskUpdate,
    MaintenanceCreate,
    HousekeepingCreate,
    GuestCreate,
    StayCreate,
    GuestRequestCreate,
    ActivityCreate,
    TransferCreate,
)
from ..security import (
    require_permission,
    ensure_feature,
    has_permission,
    entitlement_enabled,
)
from .context import guard, fingerprint
from .safety import redact


class UpdateTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: uuid.UUID
    changes: TaskUpdate


# No generic model-selected handler, permission, URL, SQL or deletion action.
CLARIFICATION = "Tell me the action you need and the guest, dates, room or staff member it concerns. I will prepare the details for you to review before anything is applied."

KINDS = {
    "propose_create_guest": (
        "create_guest",
        GuestCreate,
        "guests.manage",
        "guests",
        "_create_guest_record",
    ),
    "propose_create_stay": (
        "create_stay",
        StayCreate,
        "stays.manage",
        "stays",
        "_create_stay_record",
    ),
    "propose_create_request": (
        "create_request",
        GuestRequestCreate,
        "requests.manage",
        "guest_requests",
        "_create_request_record",
    ),
    "propose_create_activity": (
        "create_activity",
        ActivityCreate,
        "activities.manage",
        "activities",
        "_create_activity_record",
    ),
    "propose_create_transfer": (
        "create_transfer",
        TransferCreate,
        "transfers.manage",
        "transfers",
        "_create_transfer_record",
    ),
    "propose_create_task": (
        "create_task",
        TaskCreate,
        "tasks.manage",
        "tasks",
        "_create_task_record",
    ),
    "propose_update_task": (
        "update_task",
        UpdateTask,
        "tasks.view",
        "tasks",
        "_update_task_record",
    ),
    "propose_create_maintenance": (
        "create_maintenance",
        MaintenanceCreate,
        "maintenance.view",
        "maintenance",
        "_create_maintenance_record",
    ),
    "propose_create_housekeeping": (
        "create_housekeeping",
        HousekeepingCreate,
        "housekeeping.manage",
        "housekeeping",
        "_create_housekeeping_job_record",
    ),
}
BY_KIND = {entry[0]: entry for entry in KINDS.values()}
REFERENCES = {
    "unit_id": Unit,
    "assigned_staff_id": StaffProfile,
    "inspector_staff_id": StaffProfile,
    "department_id": Department,
    "guest_id": Guest,
    "stay_id": Stay,
    "guide_staff_id": StaffProfile,
    "driver_staff_id": StaffProfile,
    "vehicle_id": Vehicle,
    "asset_id": MaintenanceAsset,
    "maintenance_ticket_id": MaintenanceTicket,
}


def enabled(db, ctx, lodge_id):
    return (
        settings.ai_enabled
        and settings.ai_actions_enabled
        and has_permission(db, ctx.membership, "ai.actions")
        and entitlement_enabled(db, str(lodge_id), "ai_actions")
    )


def compact_schema(value):
    if isinstance(value, list):
        return [compact_schema(item) for item in value]
    if isinstance(value, dict):
        return {
            key: compact_schema(item)
            for key, item in value.items()
            if not (key in {"title", "description"} and isinstance(item, str))
            and key != "default"
        }
    return value


def available(db, ctx, lodge_id, scope):
    if scope != "lodge" or not enabled(db, ctx, lodge_id):
        return []
    definitions = []
    for name, (kind, schema, permission, feature, _) in KINDS.items():
        if not has_permission(
            db, ctx.membership, permission
        ) or not entitlement_enabled(db, str(lodge_id), feature):
            continue
        if kind == "update_task" and not (
            has_permission(db, ctx.membership, "tasks.manage")
            or has_permission(db, ctx.membership, "tasks.own.manage")
        ):
            continue
        if kind == "create_maintenance" and not any(
            has_permission(db, ctx.membership, p)
            for p in ["maintenance.manage", "maintenance.report"]
        ):
            continue
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": kind.replace("_", " ").capitalize()
                    + ". Propose only; in-app review and confirmation required. Use verified details; ask when uncertain.",
                    "parameters": proposal_schema(kind, schema),
                },
            }
        )
    return definitions


SELECTOR = "select_action"


def inference_tools(definitions, selected=None):
    if selected:
        return [item for item in definitions if item["function"]["name"] == selected]
    if len(definitions) <= 4:
        return definitions
    names = [item["function"]["name"] for item in definitions]
    return [
        {
            "type": "function",
            "function": {
                "name": SELECTOR,
                "description": "Choose an authorised action to obtain its input schema. This never performs a change; the selected propose tool prepares a reviewable proposal. Read tools can resolve record IDs; ask for missing or ambiguous details.",
                "parameters": {
                    "type": "object",
                    "properties": {"action": {"type": "string", "enum": names}},
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def select_action(arguments, definitions):
    if not isinstance(arguments, dict) or set(arguments) != {"action"}:
        raise HTTPException(422, "Select one supported AI action")
    name = arguments["action"]
    if not isinstance(name, str) or name not in {
        item["function"]["name"] for item in definitions
    }:
        raise HTTPException(403, "This AI action is not available to your account")
    return name


def proposal_schema(kind, schema):
    value = compact_schema(schema.model_json_schema())
    if kind == "create_guest":
        value["properties"]["email"] = {
            "type": ["string", "null"],
            "description": "Copy the exact guest_email_REF reference from the current user message, or omit when none was supplied. Never invent an email address.",
        }
    return value


def contact_input(content, enabled):
    """Raw addresses stay in this request, never persisted as chat or sent to inference."""
    import re

    contacts = {}

    def replace(match):
        ref = "guest_email_" + secrets.token_hex(8)
        contacts[ref] = match.group(0)
        return ref

    safe = (
        re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", replace, content)
        if enabled
        else content
    )
    return redact(safe), contacts


def resolve_contacts(kind, arguments, contacts):
    if kind != "create_guest" or not isinstance(arguments, dict):
        return arguments
    values = dict(arguments)
    email = values.get("email")
    if email is not None:
        if email not in contacts:
            raise HTTPException(
                422,
                "Provide the guest email in your current message, or omit it. Email addresses cannot be invented or reused from chat history.",
            )
        values["email"] = contacts[email]
    return values


def authorize(db, user, lodge_id, request, kind):
    from .principals import ReportRequest

    if isinstance(request, ReportRequest):
        raise HTTPException(403, "Background reports cannot prepare or execute actions")
    ctx = guard(db, user, lodge_id, request, write=True)
    require_permission("ai.actions", write=True)(
        lodge_id=str(lodge_id), request=request, user=ctx.user, db=db
    )
    if not enabled(db, ctx, lodge_id):
        raise HTTPException(403, "AI actions are not enabled for this lodge")
    _, _, permission, feature, _ = BY_KIND[kind]
    require_permission(permission, write=True)(
        lodge_id=str(lodge_id), request=request, user=ctx.user, db=db
    )
    ensure_feature(db, str(lodge_id), feature)
    return ctx


def parse(kind, payload):
    try:
        model = BY_KIND[kind][1].model_validate_json(json.dumps(payload))
        if (
            kind == "update_task"
            and not model.changes.model_dump(exclude_none=True, exclude_unset=True)
            and not {"vehicle_id", "maintenance_ticket_id"}.intersection(
                model.changes.model_fields_set
            )
        ):
            raise ValueError("empty changes")
        data = model.changes if kind == "update_task" else model
        if getattr(data, "title", None) is not None and len(data.title.strip()) < 2:
            raise ValueError("empty title")
        if getattr(data, "due_at", None) is not None and data.due_at.tzinfo is None:
            raise ValueError("due date needs timezone")
        if (
            getattr(data, "scheduled_for", None) is not None
            and data.scheduled_for.tzinfo is None
        ):
            raise ValueError("scheduled date needs timezone")
        for key in (
            "starts_at",
            "ends_at",
            "scheduled_at",
            "expected_end_at",
            "flight_time",
        ):
            value = getattr(data, key, None)
            if value is not None and value.tzinfo is None:
                raise ValueError("scheduled date needs timezone")
        return model
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(
            422, "The proposed action has invalid or incomplete details"
        ) from None


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def inspect(db, ctx, lodge_id, kind, model, request):
    """Use the same mutation implementation inside a rolled-back savepoint for validation.

    No outbox notification, event, record or state change survives this dry run.
    """
    from .. import main

    data = model.changes if kind == "update_task" else model
    values = data.model_dump(
        mode="json", exclude_none=True, exclude_unset=kind == "update_task"
    )
    if kind == "update_task":
        for key in ("vehicle_id", "maintenance_ticket_id"):
            if key in data.model_fields_set:
                values[key] = getattr(data, key)
                if values[key] is not None:
                    values[key] = str(values[key])
    old = {}
    snapshot = {}
    fields = []
    linked_states = []
    if kind == "update_task":
        task = main.tenant_get(db, Task, model.task_id, str(lodge_id), "Task")
        main._ensure_department_scope(ctx, task.department_id, "task")
        if not has_permission(db, ctx.membership, "tasks.manage") and not (
            ctx.staff
            and task.assigned_staff_id == ctx.staff.id
            and has_permission(db, ctx.membership, "tasks.own.manage")
        ):
            raise HTTPException(403, "You may only update tasks assigned to you")
        old = {k: getattr(task, k, None) for k in values}
        snapshot["task"] = digest(
            {c.name: getattr(task, c.name) for c in Task.__table__.columns}
        )
        fields.append({"key": "task", "value": redact(task.title)})
    guest_ids = values.pop("guest_ids", None)
    if guest_ids is not None:
        labels = []
        for guest_id in dict.fromkeys(guest_ids):
            guest = main.ensure_fk(db, Guest, guest_id, str(lodge_id), "Guest")
            if guest.anonymized_at:
                raise HTTPException(
                    409, "Anonymised guest profiles cannot be used for new AI actions"
                )
            snapshot["guest:" + guest_id] = digest(
                {c.name: getattr(guest, c.name) for c in Guest.__table__.columns}
            )
            may_name = has_permission(
                db, ctx.membership, "guests.view"
            ) and entitlement_enabled(db, str(lodge_id), "guests")
            labels.append(
                f"{redact(guest.first_name + ' ' + guest.last_name)} ({guest_id})"
                if may_name
                else guest_id
            )
        fields.append({"key": "guest_ids", "value": ", ".join(labels) or None})
    for key, value in values.items():
        if value in (None, ""):
            if kind == "update_task" and key in {"vehicle_id", "maintenance_ticket_id"}:
                fields.append(
                    {
                        "key": key,
                        "value": None,
                        "previous": str(old[key]) if old.get(key) else None,
                    }
                )
            continue
        display = value
        if key in REFERENCES:
            row = main.ensure_fk(
                db, REFERENCES[key], value, str(lodge_id), key.replace("_", " ")
            )
            if isinstance(row, StaffProfile) and row.employment_status != "active":
                raise HTTPException(
                    409, "The selected staff member is no longer active"
                )
            if isinstance(row, Guest) and row.anonymized_at:
                raise HTTPException(
                    409, "Anonymised guest profiles cannot be used for new AI actions"
                )
            snapshot[key] = digest(
                {c.name: getattr(row, c.name) for c in row.__table__.columns}
            )
            # Respect independent directory/profile permissions before disclosing labels.
            access = {
                Unit: ("units.view", "units"),
                StaffProfile: ("staff.view", "staff"),
                Guest: ("guests.view", "guests"),
                Stay: ("stays.view", "stays"),
                Vehicle: ("vehicles.view", "fleet"),
                Department: ("departments.view", "departments"),
                MaintenanceAsset: ("maintenance.view", "maintenance_workshop"),
                MaintenanceTicket: ("maintenance.view", "maintenance"),
            }
            permission, feature = access[type(row)]
            can_name = has_permission(
                db, ctx.membership, permission
            ) and entitlement_enabled(db, str(lodge_id), feature)
            if can_name and isinstance(row, (Unit, Vehicle)):
                linked_states.append(
                    (
                        row,
                        "room_status" if isinstance(row, Unit) else "vehicle_status",
                        row.status,
                    )
                )
            label = (
                (
                    getattr(row, "name", None)
                    or getattr(row, "full_name", None)
                    or getattr(row, "registration", None)
                    or getattr(row, "title", None)
                    or (
                        (row.first_name + " " + row.last_name)
                        if isinstance(row, Guest)
                        else None
                    )
                )
                if can_name
                else None
            )
            display = f"{redact(label)} ({value})" if label else str(value)
        field = {"key": key, "value": display}
        if key in old:
            field["previous"] = redact(str(old[key])) if old[key] is not None else None
        fields.append(field)
    if kind in {
        "create_task",
        "create_maintenance",
        "create_request",
        "create_activity",
        "create_transfer",
    } and not getattr(data, "department_id", None):
        staff = (
            db.get(
                StaffProfile,
                (
                    getattr(data, "assigned_staff_id", None)
                    or getattr(data, "guide_staff_id", None)
                    or getattr(data, "driver_staff_id", None)
                ),
            )
            if (
                getattr(data, "assigned_staff_id", None)
                or getattr(data, "guide_staff_id", None)
                or getattr(data, "driver_staff_id", None)
            )
            else None
        )
        department_id = main._set_department_from_staff_or_context(ctx, staff, None)
        if department_id:
            department = main.ensure_fk(
                db, Department, department_id, str(lodge_id), "Department"
            )
            may_name = has_permission(
                db, ctx.membership, "departments.view"
            ) and entitlement_enabled(db, str(lodge_id), "departments")
            fields.append(
                {
                    "key": "department_id",
                    "value": (
                        f"{redact(department.name)} ({department_id})"
                        if may_name
                        else str(department_id)
                    ),
                }
            )
            snapshot["effective_department"] = digest(
                {
                    c.name: getattr(department, c.name)
                    for c in Department.__table__.columns
                }
            )
    transaction = db.begin_nested()
    try:
        apply(db, ctx, lodge_id, kind, model, request)
        db.flush()
        for linked, key, before in linked_states:
            if linked.status != before:
                fields.append({"key": key, "value": linked.status, "previous": before})
    finally:
        transaction.rollback()
    return {"fields": fields}, snapshot


def apply(db, ctx, lodge_id, kind, model, request):
    from .. import main

    handler = getattr(main, BY_KIND[kind][4])
    args = dict(
        lodge_id=str(lodge_id),
        body=model.changes if kind == "update_task" else model,
        request=request,
        user=ctx.user,
        db=db,
    )
    if kind == "update_task":
        args["record_id"] = str(model.task_id)
    return handler(**args)


def payload(row):
    status = (
        "expired"
        if row.status == "pending" and row.expires_at <= datetime.now(timezone.utc)
        else row.status
    )
    return {
        "id": str(row.id),
        "action": row.action,
        "status": status,
        "preview": row.preview,
        "expires_at": row.expires_at.isoformat(),
        "result": row.result if row.status == "confirmed" else None,
    }


def prepare(
    db, ctx, lodge_id, conversation, request_id, name, arguments, request, contacts=None
):
    if name not in KINDS:
        raise HTTPException(422, "AI action is not registered")
    kind = KINDS[name][0]
    ctx = authorize(db, ctx.user, lodge_id, request, kind)
    if conversation.scope_type != "lodge":
        raise HTTPException(403, "Actions require a single-lodge conversation")
    if (
        db.scalar(
            select(func.count())
            .select_from(AIAction)
            .where(
                AIAction.user_id == ctx.user.id,
                AIAction.lodge_id == lodge_id,
                AIAction.status == "pending",
                AIAction.expires_at > datetime.now(timezone.utc),
            )
        )
        >= 10
    ):
        raise HTTPException(
            429, "Review or cancel existing action proposals before creating more"
        )
    model = parse(kind, resolve_contacts(kind, arguments, contacts or {}))
    preview, snapshot = inspect(db, ctx, lodge_id, kind, model, request)
    row = AIAction(
        lodge_id=lodge_id,
        user_id=ctx.user.id,
        conversation_id=conversation.id,
        request_id=request_id,
        action=kind,
        payload=model.model_dump(mode="json", exclude_unset=True),
        preview=preview,
        snapshot=snapshot,
        access_fingerprint=fingerprint(db, ctx, lodge_id),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(row)
    db.flush()
    main_audit(db, ctx, lodge_id, row.id, "proposed", request)
    return row


def main_audit(db, ctx, lodge_id, action_id, event, request):
    from .. import main

    main.audit(
        db,
        request,
        str(lodge_id),
        ctx.user.id,
        "ai.action." + event,
        "ai_action",
        str(action_id),
    )


def load(db, user, lodge_id, conversation_id, action_id, request):
    from .routes import conversation

    ctx = guard(db, user, lodge_id, request, write=True)
    conv = conversation(db, lodge_id, user, conversation_id, ctx, request)
    if conv.scope_type != "lodge":
        raise HTTPException(403, "Actions require a single-lodge conversation")
    db.execute(text("SET LOCAL lock_timeout = '5s'"))
    row = db.scalar(
        select(AIAction)
        .where(
            AIAction.id == action_id,
            AIAction.conversation_id == conversation_id,
            AIAction.user_id == user.id,
            AIAction.lodge_id == lodge_id,
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Action proposal not found")
    ctx = authorize(db, user, lodge_id, request, row.action)
    if row.access_fingerprint != fingerprint(db, ctx, lodge_id):
        raise HTTPException(409, "Your access changed. Request a new action proposal")
    return ctx, row


def review(db, ctx, row, lodge_id, request):
    if row.status != "pending" or row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            409, "This proposal is no longer pending. Request a new one"
        )
    preview, snapshot = inspect(
        db, ctx, lodge_id, row.action, parse(row.action, row.payload), request
    )
    if snapshot != row.snapshot or preview != row.preview:
        raise HTTPException(
            409, "The records changed. Request a new proposal before confirming"
        )
    token = secrets.token_urlsafe(32)
    row.token_hash = digest(token)
    db.flush()
    result = {**payload(row), "token": token}
    db.commit()
    return result


def confirm(db, ctx, row, lodge_id, token, request):
    if not row.token_hash or not secrets.compare_digest(row.token_hash, digest(token)):
        raise HTTPException(
            409, "This review link is no longer valid. Review the proposal again"
        )
    if row.status == "confirmed":
        return payload(
            row
        )  # Same consumed token may retrieve its result, never execute twice.
    if row.status != "pending" or row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            409, "This proposal has expired or was cancelled. Request a new one"
        )
    model = parse(row.action, row.payload)
    preview, snapshot = inspect(db, ctx, lodge_id, row.action, model, request)
    if snapshot != row.snapshot or preview != row.preview:
        raise HTTPException(
            409, "The records changed. Request a new proposal before confirming"
        )
    # Lock referenced rows in deterministic order, then compare again. Prevent stale record writes.
    from .. import main

    refs = [
        (REFERENCES[k], v)
        for k, v in (model.changes if row.action == "update_task" else model)
        .model_dump(mode="json", exclude_none=True)
        .items()
        if k in REFERENCES
    ]
    if row.action == "create_activity":
        refs.extend((Guest, str(gid)) for gid in model.guest_ids)
    if row.action == "update_task":
        refs.append((Task, str(model.task_id)))
        refs += [
            (GuestRequest, str(rid))
            for rid in db.scalars(
                select(GuestRequest.id).where(
                    GuestRequest.lodge_id == lodge_id,
                    GuestRequest.task_id == model.task_id,
                )
            )
        ]
    for cls, record_id in sorted(
        refs, key=lambda pair: (pair[0].__tablename__, str(pair[1]))
    ):
        db.execute(
            select(cls)
            .where(cls.id == record_id, cls.lodge_id == lodge_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
    db.expire_all()
    preview, snapshot = inspect(db, ctx, lodge_id, row.action, model, request)
    if snapshot != row.snapshot or preview != row.preview:
        raise HTTPException(
            409, "The records changed. Request a new proposal before confirming"
        )
    ctx = authorize(db, ctx.user, lodge_id, request, row.action)
    if row.access_fingerprint != fingerprint(db, ctx, lodge_id):
        raise HTTPException(409, "Your access changed. Request a new proposal")
    if row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(409, "The proposal expired. Request a new proposal")
    row.result = apply(db, ctx, lodge_id, row.action, model, request)
    if row.action == "create_guest":
        # Do not retain a second copy of guest contact/medical details after creation.
        row.result = {"id": row.result["id"]}
        row.payload = {}
        row.preview = {"fields": [{"key": "guest_id", "value": row.result["id"]}]}
    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    main_audit(db, ctx, lodge_id, row.id, "confirmed", request)
    db.flush()
    result = payload(row)
    db.commit()
    return result
