"""Actor-scoped, idempotent Celery ingestion. Never use privileged tenant RLS."""

import hashlib, uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from fastapi import HTTPException
from ..celery_app import celery_app
from ..db import SessionLocal
from ..config import settings
from ..models import AIKnowledgeDocument, AIKnowledgeChunk
from .knowledge import worker_scope
from .extraction import extract_isolated, MAX_BYTES, ExtractionError
from .embeddings import get_embeddings
from .providers.base import ProviderUnavailable


def process_document(
    lodge_id, document_id, actor_id, job_token, session_factory=SessionLocal
):
    lodge_id, document_id, actor_id, job_token = map(
        uuid.UUID, map(str, (lodge_id, document_id, actor_id, job_token))
    )
    try:
        with session_factory() as db:
            worker_scope(db, lodge_id, actor_id)
            doc = db.scalar(
                select(AIKnowledgeDocument)
                .where(AIKnowledgeDocument.id == document_id)
                .with_for_update()
            )
            if (
                not doc
                or doc.lodge_id != lodge_id
                or doc.job_token != job_token
                or doc.processing_actor_id != actor_id
                or doc.status != "queued"
            ):
                return {"status": "skipped"}
            doc.status = "processing"
            doc.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
            key, digest, kind, size = (
                doc.object_key,
                doc.sha256,
                doc.source_type,
                doc.size_bytes,
            )
            model, version = settings.ai_embedding_model, settings.ai_embedding_version
            db.commit()
        from ..main import s3_internal

        stream = s3_internal.get_object(Bucket=settings.object_storage_bucket, Key=key)[
            "Body"
        ]
        try:
            data = stream.read(MAX_BYTES + 1)
        finally:
            stream.close()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ExtractionError("checksum_mismatch")
        chunks = extract_isolated(data, kind)
        vectors = []
        provider = get_embeddings()
        for offset in range(0, len(chunks), 8):
            with session_factory() as db:
                worker_scope(db, lodge_id, actor_id)
                current = db.get(AIKnowledgeDocument, document_id)
                if (
                    not current
                    or current.status != "processing"
                    or current.job_token != job_token
                ):
                    return {"status": "cancelled"}
            vectors.extend(
                provider.embed([text for _, text in chunks[offset : offset + 8]])
            )
        with session_factory() as db:
            worker_scope(db, lodge_id, actor_id)
            doc = db.scalar(
                select(AIKnowledgeDocument)
                .where(AIKnowledgeDocument.id == document_id)
                .with_for_update()
            )
            if not doc or doc.job_token != job_token or doc.status != "processing":
                return {"status": "cancelled"}
            if (model, version) != (
                settings.ai_embedding_model,
                settings.ai_embedding_version,
            ):
                raise ExtractionError("configuration_changed")
            db.execute(
                delete(AIKnowledgeChunk).where(
                    AIKnowledgeChunk.document_id == document_id
                )
            )
            for position, ((locator, content), embedding) in enumerate(
                zip(chunks, vectors, strict=True)
            ):
                db.add(
                    AIKnowledgeChunk(
                        lodge_id=lodge_id,
                        document_id=document_id,
                        position=position,
                        locator=locator,
                        content=content,
                        embedding=embedding,
                    )
                )
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            doc.error_code = ""
            doc.embedding_model = model
            doc.embedding_version = version
            doc.lease_expires_at = None
            db.commit()
        return {"status": "ready", "chunks": len(chunks)}
    except Exception as error:
        # Store only a safe finite error category, never parser/provider/storage text.
        code = (
            str(error)
            if isinstance(error, ExtractionError)
            else (
                "embedding_unavailable"
                if isinstance(error, ProviderUnavailable)
                else (
                    "access_changed"
                    if isinstance(error, HTTPException)
                    else "processing_failed"
                )
            )
        )
        with session_factory() as db:
            try:
                worker_scope(db, lodge_id, actor_id)
                doc = db.get(AIKnowledgeDocument, document_id)
                if (
                    doc
                    and doc.job_token == job_token
                    and doc.status in {"queued", "processing"}
                ):
                    doc.status = "failed"
                    doc.error_code = code[:40]
                    doc.lease_expires_at = None
                    db.commit()
            except HTTPException:
                db.rollback()
        return {"status": "failed"}


@celery_app.task(
    name="app.ai.knowledge_jobs.ingest",
    soft_time_limit=75,
    time_limit=90,
    ignore_result=True,
)
def ingest(lodge_id, document_id, actor_id, job_token):
    return process_document(lodge_id, document_id, actor_id, job_token)
