"""No model tool can call these CSRF-protected user confirmation endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from ..db import get_db
from ..models import User
from ..security import require_permission, require_csrf
from . import actions

router = APIRouter()
BASE = (
    "/api/v1/lodges/{lodge_id}/ai/conversations/{conversation_id}/actions/{action_id}"
)


class ConfirmationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)


@router.post(BASE + "/review", dependencies=[Depends(require_csrf)])
def review_action(
    lodge_id: UUID,
    conversation_id: UUID,
    action_id: UUID,
    request: Request,
    user: User = Depends(require_permission("ai.actions", write=True)),
    db=Depends(get_db),
):
    ctx, row = actions.load(db, user, lodge_id, conversation_id, action_id, request)
    return actions.review(db, ctx, row, lodge_id, request)


@router.post(BASE + "/confirm", dependencies=[Depends(require_csrf)])
def confirm_action(
    lodge_id: UUID,
    conversation_id: UUID,
    action_id: UUID,
    body: ConfirmationIn,
    request: Request,
    user: User = Depends(require_permission("ai.actions", write=True)),
    db=Depends(get_db),
):
    ctx, row = actions.load(db, user, lodge_id, conversation_id, action_id, request)
    return actions.confirm(db, ctx, row, lodge_id, body.token, request)


@router.post(BASE + "/cancel", dependencies=[Depends(require_csrf)])
def cancel_action(
    lodge_id: UUID,
    conversation_id: UUID,
    action_id: UUID,
    request: Request,
    user: User = Depends(require_permission("ai.actions", write=True)),
    db=Depends(get_db),
):
    ctx, row = actions.load(db, user, lodge_id, conversation_id, action_id, request)
    if row.status == "pending":
        row.status = "cancelled"
        row.token_hash = None
        actions.main_audit(db, ctx, lodge_id, row.id, "cancelled", request)
    db.flush()
    result = actions.payload(row)
    db.commit()
    return result
