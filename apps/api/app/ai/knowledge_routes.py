"""Private document management, guarded independently of tool calls."""

import uuid, hashlib, re
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete, func
from ..models import User, AIKnowledgeDocument, AIKnowledgeChunk, Department
from ..db import get_db
from ..config import settings
from ..security import (
    require_permission,
    require_csrf,
    access_context,
    has_permission,
    entitlement_enabled,
    ensure_feature,
)
from .knowledge import scope, get_document, may_manage
from .extraction import MAX_BYTES
from .embeddings import configured

router = APIRouter()
TYPES = {
    "txt": "text/plain",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def payload(doc, ctx):
    outdated = doc.status == "ready" and (
        doc.embedding_model != settings.ai_embedding_model
        or doc.embedding_version != settings.ai_embedding_version
    )
    return {
        key: getattr(doc, key)
        for key in (
            "id",
            "title",
            "file_name",
            "source_type",
            "visibility",
            "department_id",
            "status",
            "chunk_count",
            "created_at",
            "updated_at",
        )
    } | {
        "status": "outdated" if outdated else doc.status,
        "can_manage": may_manage(ctx, doc),
        "can_retry": outdated
        or doc.status in {"uploaded", "failed"}
        or (
            doc.status in {"queued", "processing"}
            and doc.lease_expires_at
            and doc.lease_expires_at < datetime.now(timezone.utc)
        ),
    }


def checked(db, user, lodge_id, request, write=False):
    return scope(db, access_context(db, user, str(lodge_id)), lodge_id, request, write)


def visibility_scope(ctx, visibility, department_id, db, lodge_id):
    if visibility == "department":
        ensure_feature(db, str(lodge_id), "departments")
        dep = db.get(Department, department_id) if department_id else None
        if not dep or dep.lodge_id != lodge_id or not dep.is_active:
            raise HTTPException(422, "Choose an active department in this lodge")
        if (
            ctx.role_key not in {"lodge_admin", "group_admin"}
            and ctx.department_id != dep.id
        ):
            raise HTTPException(403, "You cannot share outside your department")
    elif department_id is not None:
        raise HTTPException(422, "A department is only used for department sharing")
    if visibility == "lodge" and ctx.role_key not in {"lodge_admin", "group_admin"}:
        raise HTTPException(
            403, "Lodge-wide sharing requires lodge administrator access"
        )


@router.get("/api/v1/lodges/{lodge_id}/ai/knowledge")
def list_documents(
    lodge_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("knowledge.view")),
    db=Depends(get_db),
):
    ctx = checked(db, user, lodge_id, request)
    rows = db.scalars(
        select(AIKnowledgeDocument)
        .where(
            AIKnowledgeDocument.lodge_id == lodge_id,
            AIKnowledgeDocument.status != "deleted",
        )
        .order_by(AIKnowledgeDocument.created_at.desc())
        .limit(101)
    ).all()
    departments = []
    if has_permission(db, ctx.membership, "knowledge.manage") and entitlement_enabled(
        db, str(lodge_id), "departments"
    ):
        query = select(Department).where(
            Department.lodge_id == lodge_id, Department.is_active.is_(True)
        )
        if ctx.role_key not in {"lodge_admin", "group_admin"}:
            query = query.where(Department.id == ctx.department_id)
        departments = [
            {"id": str(d.id), "name": d.name}
            for d in db.scalars(query.order_by(Department.name).limit(100))
        ]
    return {
        "departments": departments,
        "can_share_lodge": ctx.role_key in {"lodge_admin", "group_admin"},
        "items": [payload(doc, ctx) for doc in rows[:100]],
        "partial": len(rows) > 100,
        "processing_available": configured(),
    }


@router.post(
    "/api/v1/lodges/{lodge_id}/ai/knowledge", dependencies=[Depends(require_csrf)]
)
def upload_document(
    lodge_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=160),
    visibility: Literal["private", "department", "lodge"] = Form("private"),
    department_id: uuid.UUID | None = Form(None),
    user: User = Depends(require_permission("knowledge.manage", write=True)),
    db=Depends(get_db),
):
    ctx = checked(db, user, lodge_id, request, True)
    visibility_scope(ctx, visibility, department_id, db, lodge_id)
    # Limit storage abuse as well as parser work. Private deleted blobs are cleaned
    # best-effort; deleted metadata still counts towards this conservative cap.
    if (
        db.scalar(
            select(func.count())
            .select_from(AIKnowledgeDocument)
            .where(AIKnowledgeDocument.lodge_id == lodge_id)
        )
        >= 100
    ):
        raise HTTPException(409, "Document limit reached. Contact your administrator")
    name = re.split(r"[/\\]", file.filename or "")[-1][:160]
    kind = name.rsplit(".", 1)[-1].lower()
    if kind not in TYPES or file.content_type not in {
        TYPES.get(kind),
        "application/octet-stream",
    }:
        raise HTTPException(422, "Choose a PDF, DOCX or UTF-8 TXT file")
    data = file.file.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(422, "Choose a non-empty file up to 10 MB")
    if (kind == "pdf" and not data.startswith(b"%PDF-")) or (
        kind == "docx" and not data.startswith(b"PK")
    ):
        raise HTTPException(422, "The file does not match its format")
    title = title.strip()
    if not title:
        raise HTTPException(422, "Enter a document title")
    doc = AIKnowledgeDocument(
        id=uuid.uuid4(),
        lodge_id=lodge_id,
        created_by=user.id,
        title=title,
        file_name=name,
        source_type=kind,
        visibility=visibility,
        department_id=department_id,
        object_key="",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
    doc.object_key = f"lodges/{lodge_id}/knowledge/{doc.id}.{kind}"
    from ..main import s3_internal, audit

    try:
        s3_internal.put_object(
            Bucket=settings.object_storage_bucket,
            Key=doc.object_key,
            Body=data,
            ContentType=TYPES[kind],
            Metadata={"sha256": doc.sha256},
        )
    except Exception:
        raise HTTPException(503, "Document storage is unavailable") from None
    # Refresh authentication after storage I/O, before publishing metadata.
    ctx = checked(db, user, lodge_id, request, True)
    visibility_scope(ctx, visibility, department_id, db, lodge_id)
    db.add(doc)
    db.flush()
    audit(
        db,
        request,
        lodge_id,
        user.id,
        "knowledge.uploaded",
        "knowledge_document",
        str(doc.id),
    )
    result = payload(doc, ctx)
    db.commit()
    return result


class Sharing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visibility: Literal["private", "department", "lodge"]
    department_id: uuid.UUID | None = None


@router.patch(
    "/api/v1/lodges/{lodge_id}/ai/knowledge/{document_id}",
    dependencies=[Depends(require_csrf)],
)
def share_document(
    lodge_id: uuid.UUID,
    document_id: uuid.UUID,
    body: Sharing,
    request: Request,
    user: User = Depends(require_permission("knowledge.manage", write=True)),
    db=Depends(get_db),
):
    ctx = checked(db, user, lodge_id, request, True)
    doc = get_document(db, document_id, lodge_id)
    if not may_manage(ctx, doc):
        raise HTTPException(403, "You cannot change this document")
    # Only the creator can make a shared document private: no ownership transfer.
    if body.visibility == "private" and doc.created_by != user.id:
        raise HTTPException(403, "Only the creator can make this document private")
    visibility_scope(ctx, body.visibility, body.department_id, db, lodge_id)
    doc.visibility = body.visibility
    doc.department_id = body.department_id
    from ..main import audit

    audit(
        db,
        request,
        lodge_id,
        user.id,
        "knowledge.visibility_changed",
        "knowledge_document",
        str(doc.id),
    )
    db.commit()
    return {"status": "updated"}


@router.post(
    "/api/v1/lodges/{lodge_id}/ai/knowledge/{document_id}/process",
    dependencies=[Depends(require_csrf)],
)
def queue_document(
    lodge_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("knowledge.manage", write=True)),
    db=Depends(get_db),
):
    ctx = checked(db, user, lodge_id, request, True)
    if not configured():
        raise HTTPException(503, "Document processing is not configured")
    doc = get_document(db, document_id, lodge_id)
    if not may_manage(ctx, doc):
        raise HTTPException(403, "You cannot process this document")
    # Lock after the visibility check, to make double-click/concurrent retries safe.
    doc = db.scalar(
        select(AIKnowledgeDocument)
        .where(AIKnowledgeDocument.id == document_id)
        .with_for_update()
    )
    if not payload(doc, ctx)["can_retry"]:
        raise HTTPException(409, "This document is already processed or processing")
    token = uuid.uuid4()
    doc.status = "queued"
    doc.job_token = token
    doc.processing_actor_id = user.id
    doc.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
    doc.error_code = ""
    from ..main import audit

    audit(
        db,
        request,
        lodge_id,
        user.id,
        "knowledge.processing_requested",
        "knowledge_document",
        str(doc.id),
    )
    db.commit()
    from .knowledge_jobs import ingest

    try:
        ingest.delay(str(lodge_id), str(document_id), str(user.id), str(token))
    except Exception:
        checked(db, user, lodge_id, request, True)
        doc = get_document(db, document_id, lodge_id)
        if doc.job_token == token and doc.status == "queued":
            doc.status = "failed"
            doc.error_code = "queue_unavailable"
            db.commit()
        raise HTTPException(
            503, "Document processing is temporarily unavailable. Try again"
        ) from None
    return {"status": "queued"}


@router.get("/api/v1/lodges/{lodge_id}/ai/knowledge/{document_id}/download")
def download_document(
    lodge_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("knowledge.view")),
    db=Depends(get_db),
):
    checked(db, user, lodge_id, request)
    doc = get_document(db, document_id, lodge_id)
    # Never serve unprocessed/quarantined originals or expose arbitrary object keys.
    if doc.status != "ready":
        raise HTTPException(409, "Document is not ready for download")
    from ..main import s3_public

    return {
        "url": s3_public.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.object_storage_bucket,
                "Key": doc.object_key,
                "ResponseContentDisposition": "attachment",
            },
            ExpiresIn=60,
        ),
        "expires_in_seconds": 60,
    }


@router.delete(
    "/api/v1/lodges/{lodge_id}/ai/knowledge/{document_id}",
    dependencies=[Depends(require_csrf)],
)
def remove_document(
    lodge_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("knowledge.manage", write=True)),
    db=Depends(get_db),
):
    ctx = checked(db, user, lodge_id, request, True)
    doc = get_document(db, document_id, lodge_id)
    if not may_manage(ctx, doc):
        raise HTTPException(403, "You cannot remove this document")
    doc.status = "deleted"
    doc.job_token = None
    db.execute(delete(AIKnowledgeChunk).where(AIKnowledgeChunk.document_id == doc.id))
    from ..main import audit, s3_internal

    key = doc.object_key
    audit(
        db,
        request,
        lodge_id,
        user.id,
        "knowledge.removed",
        "knowledge_document",
        str(doc.id),
    )
    db.commit()
    try:
        s3_internal.delete_object(Bucket=settings.object_storage_bucket, Key=key)
    except Exception:
        pass  # Remains private and excluded; operator cleanup is documented.
    return {"status": "removed"}
