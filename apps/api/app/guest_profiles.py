"""Guest CRM additions. Records prior interactions; never sends email/messages."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .db import get_db
from .models import Guest, GuestCommunication, User
from .schemas import StrictModel
from .security import ensure_feature, require_csrf, require_permission

router = APIRouter()
BASE = "/api/v1/lodges/{lodge_id}/guests/{record_id}/communications"


def details(guest):
    return {
        "birthday": guest.birthday.isoformat() if guest.birthday else None,
        "anniversary": guest.anniversary.isoformat() if guest.anniversary else None,
        "repeat_guest": guest.repeat_guest,
        "safari_preferences": guest.safari_preferences,
        "anonymized_at": (
            guest.anonymized_at.isoformat() if guest.anonymized_at else None
        ),
    }


def lock_guest(db, lodge_id, record_id):
    from .main import tenant_get

    guest = tenant_get(db, Guest, record_id, lodge_id, "Guest")
    db.refresh(guest, with_for_update=True)
    return guest


def redact_communications(db, guest):
    db.execute(
        update(GuestCommunication)
        .where(
            GuestCommunication.lodge_id == guest.lodge_id,
            GuestCommunication.guest_id == guest.id,
        )
        .values(subject="", message="", redacted_at=guest.anonymized_at)
    )


def serialize(row):
    return {
        "id": str(row.id),
        "channel": row.channel,
        "direction": row.direction,
        "subject": row.subject,
        "message": row.message,
        "occurred_at": row.occurred_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "redacted_at": row.redacted_at.isoformat() if row.redacted_at else None,
    }


def export_communications(db, guest):
    return [
        serialize(row)
        for row in db.scalars(
            select(GuestCommunication)
            .where(
                GuestCommunication.lodge_id == guest.lodge_id,
                GuestCommunication.guest_id == guest.id,
            )
            .order_by(GuestCommunication.occurred_at, GuestCommunication.id)
        )
    ]


class CommunicationIn(StrictModel):
    client_reference: UUID
    channel: Literal["email", "phone", "in_person", "whatsapp", "other"]
    direction: Literal["inbound", "outbound", "internal"]
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    occurred_at: datetime | None = None

    @field_validator("subject", "message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a description")
        return value.strip()

    @field_validator("occurred_at")
    @classmethod
    def prior_interaction(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Include a time zone")
            if value > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError("Interaction time cannot be in the future")
        return value


@router.get(BASE)
def list_communications(
    lodge_id: UUID,
    record_id: UUID,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission("guests.view")),
    db: Session = Depends(get_db),
):
    from .main import tenant_get

    ensure_feature(db, str(lodge_id), "guests")
    guest = tenant_get(db, Guest, record_id, lodge_id, "Guest")
    rows = db.scalars(
        select(GuestCommunication)
        .where(
            GuestCommunication.lodge_id == guest.lodge_id,
            GuestCommunication.guest_id == guest.id,
        )
        .order_by(GuestCommunication.occurred_at.desc(), GuestCommunication.id.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [serialize(row) for row in rows[:limit]],
        "has_more": len(rows) > limit,
    }


@router.post(BASE, dependencies=[Depends(require_csrf)])
def log_communication(
    lodge_id: UUID,
    record_id: UUID,
    body: CommunicationIn,
    request: Request,
    user: User = Depends(require_permission("guests.manage", write=True)),
    db: Session = Depends(get_db),
):
    from .main import audit, event

    ensure_feature(db, str(lodge_id), "guests")
    # Serialise against retries and anonymisation; a redaction cannot race a new note.
    guest = lock_guest(db, lodge_id, record_id)
    if guest.anonymized_at:
        raise HTTPException(409, "Anonymised profiles cannot receive new interactions")
    existing = db.scalar(
        select(GuestCommunication).where(
            GuestCommunication.lodge_id == lodge_id,
            GuestCommunication.guest_id == record_id,
            GuestCommunication.client_reference == body.client_reference,
        )
    )
    if existing:
        if any(
            getattr(existing, key) != getattr(body, key)
            for key in ("channel", "direction", "subject", "message")
        ) or (body.occurred_at and body.occurred_at != existing.occurred_at):
            raise HTTPException(409, "This interaction reference has already been used")
        return serialize(existing)
    row = GuestCommunication(
        lodge_id=lodge_id,
        guest_id=record_id,
        created_by_user_id=user.id,
        **body.model_dump(exclude={"occurred_at"}),
        occurred_at=body.occurred_at or datetime.now(timezone.utc)
    )
    db.add(row)
    db.flush()
    # No message contents, subject, contact details or occasions enter general memory/audit.
    audit(
        db,
        request,
        lodge_id,
        user.id,
        "guest.communication_logged",
        "guest",
        str(guest.id),
    )
    event(
        db,
        lodge_id,
        user.id,
        "guest.communication_logged",
        "guest",
        str(guest.id),
        "Guest interaction recorded",
    )
    db.commit()
    return serialize(row)
