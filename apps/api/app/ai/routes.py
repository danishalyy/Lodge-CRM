"""Private lodge AI APIs; provider failures never affect core application startup."""

import json, time, uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from ..config import settings
from ..db import get_db, set_rls_context
from ..models import (
    Lodge,
    AIConversation,
    AIMessage,
    AIUsage,
    AIToolExecution,
    AIAction,
    AuditLog,
    User,
)
from ..security import (
    require_permission,
    require_csrf,
    has_permission,
    entitlement_enabled,
)
from .context import guard, fingerprint
from .configuration import configuration_state, get_provider, health_ready
from .providers.base import ProviderUnavailable
from .limits import admission
from .safety import SYSTEM, redact
from . import tools, actions, reports
from .provenance import source_for
from .groups import (
    resolve as resolve_group,
    conversation_fingerprint as fingerprint_for,
    summarise as summarise_group,
)
from .memory import verify_sources as verify_memory_sources
from .knowledge import verify_sources as verify_document_sources


def verify_sources(sources, db, ctx, lodge_id, request):
    verify_memory_sources(sources, db, ctx, lodge_id, request)
    verify_document_sources(sources, db, ctx, lodge_id, request)


router = APIRouter()


class ConversationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["lodge", "group"] = "lodge"


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    content: str = Field(min_length=1, max_length=3000)


def provider_dependency():
    try:
        return get_provider()
    except ProviderUnavailable:
        raise HTTPException(
            503, "Lodge AI is not configured or is unavailable"
        ) from None


def conversation(db, lodge_id, user, conversation_id, ctx, request):
    row = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.lodge_id == lodge_id,
            AIConversation.user_id == user.id,
        )
    )
    if not row or row.origin != "chat":
        raise HTTPException(404, "Conversation not found")
    if row.access_fingerprint != fingerprint_for(
        db, ctx, lodge_id, request, row.scope_type, row.group_id
    ):
        raise HTTPException(
            409,
            "Your access changed. Start a new conversation to use your current permissions",
        )
    return row


def message_payload(row, db=None):
    value = {
        "id": str(row.id),
        "request_id": str(row.request_id),
        "role": row.role,
        "content": row.content,
        "sources": row.sources,
        "created_at": row.created_at.isoformat(),
    }
    if db is not None:
        proposals = (
            db.scalars(
                select(AIAction).where(
                    AIAction.conversation_id == row.conversation_id,
                    AIAction.request_id == row.request_id,
                )
            ).all()
            if row.role == "assistant"
            else []
        )
        if proposals:
            value["actions"] = [actions.payload(p) for p in proposals]
    return value


def audit(db, user, lodge_id, action, request_id, request):
    db.add(
        AuditLog(
            lodge_id=lodge_id,
            actor_user_id=user.id,
            action=action,
            resource_type="ai_request",
            resource_id=str(request_id),
            request_id=request.headers.get("x-request-id", ""),
            detail="",
        )
    )


@router.get("/api/v1/lodges/{lodge_id}/ai/status")
def status(
    lodge_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("ai.use")),
    db=Depends(get_db),
    scope: Literal["lodge", "group"] = "lodge",
):
    ctx = guard(db, user, lodge_id, request)
    group = resolve_group(db, user, lodge_id, request) if scope == "group" else None
    state = configuration_state()
    ready = False
    if state == "configured":
        db.rollback()
        ready = health_ready()
        ctx = guard(db, user, lodge_id, request)
        group = resolve_group(db, user, lodge_id, request) if scope == "group" else None
    return {
        "scope": {
            "lodge_id": str(lodge_id),
            "lodge_name": db.get(Lodge, lodge_id).name,
            "type": scope,
            **(
                {
                    key: group[key]
                    for key in ("group_id", "group_name", "lodges", "excluded_count")
                }
                if group
                else {}
            ),
        },
        "state": (
            "ready" if ready else "unavailable" if state == "configured" else state
        ),
        "knowledge_enabled": bool(
            scope == "lodge"
            and settings.ai_knowledge_enabled
            and has_permission(db, ctx.membership, "knowledge.view")
            and entitlement_enabled(db, str(lodge_id), "ai_knowledge")
            and entitlement_enabled(db, str(lodge_id), "document_knowledge")
        ),
        "report_kinds": reports.available(db, ctx, lodge_id),
        "provider": settings.ai_provider,
        "tools": [
            {
                "name": x["function"]["name"],
                "description": x["function"]["description"],
                "suggestion": tools.REGISTRY[x["function"]["name"]].suggestion,
            }
            for x in tools.available(db, ctx, lodge_id, scope)
        ]
        + [
            {
                "name": x["function"]["name"],
                "description": x["function"]["description"],
                "suggestion": None,
            }
            for x in actions.available(db, ctx, lodge_id, scope)
        ],
    }


@router.get("/api/v1/lodges/{lodge_id}/ai/conversations")
def conversations(
    lodge_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("ai.use")),
    db=Depends(get_db),
    scope: Literal["lodge", "group"] = "lodge",
):
    ctx = guard(db, user, lodge_id, request)
    group = resolve_group(db, user, lodge_id, request) if scope == "group" else None
    signature = group["fingerprint"] if group else fingerprint(db, ctx, lodge_id)
    # A title is the owner's first question, never assistant-sourced CRM facts.
    # The correlated read retains message owner/tenant RLS and current ACL filtering.
    first_question = (
        select(AIMessage.content)
        .where(AIMessage.conversation_id == AIConversation.id, AIMessage.role == "user")
        .order_by(AIMessage.created_at, AIMessage.id)
        .limit(1)
        .correlate(AIConversation)
        .scalar_subquery()
    )
    rows = db.execute(
        select(AIConversation, first_question.label("first_question"))
        .where(
            AIConversation.lodge_id == lodge_id,
            AIConversation.user_id == user.id,
            AIConversation.access_fingerprint == signature,
            AIConversation.scope_type == scope,
            AIConversation.origin == "chat",
        )
        .order_by(AIConversation.created_at.desc())
        .limit(30)
    ).all()
    return [
        {
            "id": str(row.id),
            "created_at": row.created_at.isoformat(),
            "title": " ".join(redact(question or "").split())[:100] or None,
        }
        for row, question in rows
    ]


@router.post(
    "/api/v1/lodges/{lodge_id}/ai/conversations", dependencies=[Depends(require_csrf)]
)
def create_conversation(
    lodge_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("ai.use", write=True)),
    db=Depends(get_db),
    body: ConversationIn | None = None,
):
    ctx = guard(db, user, lodge_id, request, write=True)
    if configuration_state() not in {"configured", "test_only"}:
        raise HTTPException(503, "Lodge AI is not configured or is unavailable")
    scope_type = body.scope if body else "lodge"
    group = (
        resolve_group(db, user, lodge_id, request) if scope_type == "group" else None
    )
    row = AIConversation(
        lodge_id=lodge_id,
        user_id=user.id,
        access_fingerprint=(
            group["fingerprint"] if group else fingerprint(db, ctx, lodge_id)
        ),
        scope_type=scope_type,
        group_id=uuid.UUID(group["group_id"]) if group else None,
    )
    db.add(row)
    db.flush()
    value = {"id": str(row.id), "created_at": row.created_at.isoformat()}
    db.commit()
    return value


@router.get("/api/v1/lodges/{lodge_id}/ai/conversations/{conversation_id}/messages")
def messages(
    lodge_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("ai.use")),
    db=Depends(get_db),
):
    ctx = guard(db, user, lodge_id, request)
    conversation(db, lodge_id, user, conversation_id, ctx, request)
    rows = db.scalars(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id)
        .limit(100)
    ).all()
    verify_sources(
        [source for row in rows for source in row.sources], db, ctx, lodge_id, request
    )
    return [message_payload(row, db) for row in reversed(rows)]


@router.post(
    "/api/v1/lodges/{lodge_id}/ai/conversations/{conversation_id}/messages",
    dependencies=[Depends(require_csrf)],
)
def send_message(
    lodge_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: MessageIn,
    request: Request,
    user: User = Depends(require_permission("ai.use", write=True)),
    db=Depends(get_db),
    provider=Depends(provider_dependency),
):
    ctx = guard(db, user, lodge_id, request, write=True)
    conv = conversation(db, lodge_id, user, conversation_id, ctx, request)
    expected = conv.access_fingerprint
    scope_type, group_id = conv.scope_type, conv.group_id
    content = redact(body.content.strip())
    if not content:
        raise HTTPException(422, "Enter a question")
    with admission(user.id, lodge_id):
        previous = db.scalar(
            select(AIUsage).where(
                AIUsage.conversation_id == conversation_id,
                AIUsage.request_id == body.request_id,
            )
        )
        if previous:
            if previous.status == "complete":
                answer = db.scalar(
                    select(AIMessage).where(
                        AIMessage.conversation_id == conversation_id,
                        AIMessage.request_id == body.request_id,
                        AIMessage.role == "assistant",
                    )
                )
                verify_sources(answer.sources, db, ctx, lodge_id, request)
                return message_payload(answer, db)
            raise HTTPException(
                409,
                "This AI request was already submitted. Start a new request to try again",
            )
        usage = AIUsage(
            lodge_id=lodge_id,
            user_id=user.id,
            conversation_id=conversation_id,
            request_id=body.request_id,
            provider=settings.ai_provider,
            model=settings.vllm_model[:200],
        )
        db.add(usage)
        db.add(
            AIMessage(
                lodge_id=lodge_id,
                user_id=user.id,
                conversation_id=conversation_id,
                request_id=body.request_id,
                role="user",
                content=content,
            )
        )
        db.commit()
        set_rls_context(db, str(lodge_id), False, str(user.id))
        history = db.scalars(
            select(AIMessage)
            .where(
                AIMessage.conversation_id == conversation_id, AIMessage.role == "user"
            )
            .order_by(AIMessage.created_at.desc())
            .limit(6)
        ).all()
        prompt = [{"role": "system", "content": SYSTEM}] + [
            {"role": "user", "content": m.content} for m in reversed(history)
        ]
        started = time.monotonic()
        sources = []
        input_tokens = 0
        output_tokens = 0
        tool_count = 0
        rejected_tool = None
        try:
            for turn in range(settings.ai_max_rounds):
                ctx = guard(db, user, lodge_id, request, write=True)
                if (
                    fingerprint_for(db, ctx, lodge_id, request, scope_type, group_id)
                    != expected
                ):
                    raise HTTPException(
                        409, "Your access changed. Start a new conversation"
                    )
                approved = tools.available(
                    db, ctx, lodge_id, scope_type
                ) + actions.available(db, ctx, lodge_id, scope_type)
                # Conservative byte budget, including schemas, reserved output and structured context.
                if (
                    len(
                        json.dumps(
                            [prompt, approved],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode()
                    )
                    > settings.ai_max_context - settings.ai_max_output_tokens
                ):
                    raise HTTPException(
                        413, "AI context limit reached. Start a shorter conversation"
                    )
                db.rollback()  # Do not hold a database transaction while the GPU is working.
                reply = provider.complete(prompt, approved)
                input_tokens += reply.input_tokens
                output_tokens += reply.output_tokens
                if not reply.tool_calls:
                    answer_text = reply.content
                    if not sources:
                        if any(
                            t["function"]["name"] in actions.KINDS for t in approved
                        ):
                            # Never publish an ungrounded model answer, including a claimed write.
                            # A fixed clarification lets action conversations collect missing details.
                            answer_text = actions.CLARIFICATION
                        else:
                            raise ProviderUnavailable("no_operational_sources")
                    ctx = guard(db, user, lodge_id, request, write=True)
                    if (
                        fingerprint_for(
                            db, ctx, lodge_id, request, scope_type, group_id
                        )
                        != expected
                    ):
                        raise HTTPException(
                            409, "Your access changed. Start a new conversation"
                        )
                    verify_sources(sources, db, ctx, lodge_id, request)
                    answer = AIMessage(
                        lodge_id=lodge_id,
                        user_id=user.id,
                        conversation_id=conversation_id,
                        request_id=body.request_id,
                        role="assistant",
                        content=redact(answer_text),
                        sources=sources,
                    )
                    db.add(answer)
                    usage = db.get(AIUsage, usage.id)
                    usage.status = "complete"
                    usage.input_tokens = input_tokens
                    usage.output_tokens = output_tokens
                    usage.tool_count = tool_count
                    usage.latency_ms = int((time.monotonic() - started) * 1000)
                    audit(
                        db,
                        user,
                        lodge_id,
                        "ai.request.completed",
                        body.request_id,
                        request,
                    )
                    db.flush()
                    result = message_payload(answer)
                    db.commit()
                    return result
                call = reply.tool_calls[0]
                ctx = guard(db, user, lodge_id, request, write=True)
                if (
                    fingerprint_for(db, ctx, lodge_id, request, scope_type, group_id)
                    != expected
                ):
                    raise HTTPException(
                        409, "Your access changed. Start a new conversation"
                    )
                tool_count += 1
                rejected_tool = (
                    call.name[:80] if isinstance(call.name, str) else "invalid_tool"
                )
                if call.name in actions.KINDS:
                    # The model creates only a proposal; it never receives a confirmation token.
                    proposal = actions.prepare(
                        db,
                        ctx,
                        lodge_id,
                        conv,
                        body.request_id,
                        call.name,
                        call.arguments,
                        request,
                    )
                    answer = AIMessage(
                        lodge_id=lodge_id,
                        user_id=user.id,
                        conversation_id=conversation_id,
                        request_id=body.request_id,
                        role="assistant",
                        content="Review the proposed change below. Nothing has been changed yet.",
                        sources=sources,
                    )
                    db.add(answer)
                    db.add(
                        AIToolExecution(
                            lodge_id=lodge_id,
                            user_id=user.id,
                            conversation_id=conversation_id,
                            request_id=body.request_id,
                            name=call.name,
                            status="proposed",
                        )
                    )
                    usage = db.get(AIUsage, usage.id)
                    usage.status = "complete"
                    usage.input_tokens = input_tokens
                    usage.output_tokens = output_tokens
                    usage.tool_count = tool_count
                    usage.latency_ms = int((time.monotonic() - started) * 1000)
                    audit(
                        db,
                        user,
                        lodge_id,
                        "ai.request.completed",
                        body.request_id,
                        request,
                    )
                    db.flush()
                    result = message_payload(answer, db)
                    db.commit()
                    return result
                result = tools.execute(
                    call.name, call.arguments, db, ctx, lodge_id, request, scope_type
                )
                remaining = (
                    settings.ai_max_context
                    - settings.ai_max_output_tokens
                    - len(
                        json.dumps(
                            [prompt, approved],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode()
                    )
                    - 1024
                )
                if "items" in result:
                    while (
                        result["items"]
                        and len(json.dumps(result, ensure_ascii=False).encode())
                        > remaining
                    ):
                        result["items"].pop()
                        result["partial"] = True
                        if tools.REGISTRY[call.name].source_kind == "group":
                            result["comparisons"] = summarise_group(result["items"])
                    result["returned_count"] = len(result["items"])
                if len(json.dumps(result, ensure_ascii=False).encode()) > remaining:
                    raise HTTPException(
                        413,
                        "The operational result exceeds the AI context limit. Ask a narrower question",
                    )
                db.add(
                    AIToolExecution(
                        lodge_id=lodge_id,
                        user_id=user.id,
                        conversation_id=conversation_id,
                        request_id=body.request_id,
                        name=call.name,
                        status="success",
                    )
                )
                db.commit()
                rejected_tool = None
                source = source_for(call.name, result, lodge_id)
                sources.append(source)
                prompt.extend(
                    [
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "type": "function",
                                    "function": {
                                        "name": call.name,
                                        "arguments": json.dumps(call.arguments),
                                    },
                                }
                            ],
                        },
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        },
                    ]
                )
            raise ProviderUnavailable("tool_round_limit")
        except (ProviderUnavailable, HTTPException) as error:
            db.rollback()
            set_rls_context(db, str(lodge_id), False, str(user.id))
            if rejected_tool:
                db.add(
                    AIToolExecution(
                        lodge_id=lodge_id,
                        user_id=user.id,
                        conversation_id=conversation_id,
                        request_id=body.request_id,
                        name=rejected_tool,
                        status="denied",
                    )
                )
            failed = db.get(AIUsage, usage.id)
            if failed:
                failed.status = "failed"
                failed.error_code = (
                    error.code
                    if isinstance(error, ProviderUnavailable)
                    else "access_or_validation_rejected"
                )
                failed.latency_ms = int((time.monotonic() - started) * 1000)
                failed.tool_count = tool_count
                failed.input_tokens = input_tokens
                failed.output_tokens = output_tokens
            audit(db, user, lodge_id, "ai.request.failed", body.request_id, request)
            db.commit()
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(
                503,
                "Lodge AI could not retrieve a reliable answer. Please try again shortly",
            ) from None
