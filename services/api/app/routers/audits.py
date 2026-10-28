"""
Audits endpoints:
  POST   /projects/{project_id}/audits
  GET    /audits
  GET    /audits/{audit_id}
  GET    /audits/{audit_id}/events   (SSE)
  POST   /audits/{audit_id}/cancel
  DELETE /audits/{audit_id}
  GET    /audits/{audit_id}/files
  GET    /audits/{audit_id}/files/{file_id}
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.storage import get_storage_client
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal, set_rls_org
from app.config import get_settings
from app.db import Audit, AuditEvent, AuditFile, Project, Upload, get_db_session, get_session_factory
from app.errors import AppError, audit_purged, not_found, feature_not_enabled
from app.logging_config import get_logger
from auditor_schemas.constants import STANDARD_DISCLAIMER

router = APIRouter(tags=["audits"])
logger = get_logger(__name__)

ALLOWED_FEATURES = {"privilege_map", "findings", "rag", "patches"}
FUTURE_FEATURES = {"proofs", "invariants"}


class AuditOptions(BaseModel):
    solc_version: str | None = None
    features: list[str] = ["privilege_map", "findings"]
    include_dependencies: bool = False
    retention_hours: int | None = None


class RoleDeclarationInput(BaseModel):
    role_key: str
    holder_type: str
    threshold: int | None = None
    signers: int | None = None
    delay_hours: float | None = None


class CreateAuditRequest(BaseModel):
    upload_id: uuid.UUID
    options: AuditOptions = AuditOptions()
    role_declarations: list[RoleDeclarationInput] = []


def _format_audit(audit: Audit) -> dict[str, Any]:
    return {
        "id": str(audit.id),
        "project_id": str(audit.project_id),
        "status": audit.status,
        "stage": audit.stage,
        "options": audit.options,
        "compiler_version": audit.compiler_version,
        "toolchain": audit.toolchain,
        "corpus_version": audit.corpus_version,
        "coverage": audit.coverage,
        "scores": audit.scores,
        "counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "error": audit.error,
        "created_at": audit.created_at.isoformat(),
        "started_at": audit.started_at.isoformat() if audit.started_at else None,
        "finished_at": audit.finished_at.isoformat() if audit.finished_at else None,
        "purge_after": audit.purge_after.isoformat(),
        "disclaimer": STANDARD_DISCLAIMER,
    }


@router.post("/projects/{project_id}/audits", status_code=202)
async def create_audit(
    project_id: uuid.UUID,
    body: CreateAuditRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()

    # Validate features
    for f in body.options.features:
        if f in FUTURE_FEATURES:
            raise feature_not_enabled(f)
        if f not in ALLOWED_FEATURES:
            raise AppError("VALIDATION_ERROR", f"Unknown feature: {f!r}", 422)

    # Check project exists and belongs to org
    project = await session.get(Project, project_id)
    if not project or project.org_id != principal.org_id or project.deleted_at:
        raise not_found("Project", str(project_id))

    # Check upload exists and belongs to org
    upload = await session.get(Upload, body.upload_id)
    if not upload or upload.org_id != principal.org_id:
        raise not_found("Upload", str(body.upload_id))

    retention_hours = body.options.retention_hours or settings.default_retention_hours
    purge_after = datetime.utcnow() + timedelta(hours=retention_hours)

    audit = Audit(
        org_id=principal.org_id,
        project_id=project_id,
        created_by=principal.user_id,
        upload_id=body.upload_id,
        status="queued",
        options=body.options.model_dump(),
        purge_after=purge_after,
    )
    session.add(audit)
    await session.flush()

    # Emit initial event
    event = AuditEvent(
        audit_id=audit.id,
        org_id=principal.org_id,
        stage=None,
        level="info",
        message="Audit queued",
        data={"status": "queued"},
    )
    session.add(event)
    await session.commit()

    # Enqueue the worker job (local background task or Arq/Redis)
    if settings.queue_backend == "local" or not settings.redis_url:
        import asyncio
        from app.worker_local import run_local_audit_pipeline
        asyncio.create_task(
            run_local_audit_pipeline(
                str(audit.id),
                str(principal.org_id),
                body.options.model_dump(),
                [d.model_dump() for d in body.role_declarations],
            )
        )
    else:
        import arq
        redis_pool = await arq.create_pool(settings.redis_url)
        await redis_pool.enqueue_job(
            "run_audit_pipeline",
            str(audit.id),
            str(principal.org_id),
            body.options.model_dump(),
            [d.model_dump() for d in body.role_declarations],
        )

    logger.info("audit_queued", audit_id=str(audit.id), org_id=str(principal.org_id))

    return {
        "audit_id": str(audit.id),
        "status": "queued",
        "events_url": f"/v1/audits/{audit.id}/events",
    }


@router.get("/audits")
async def list_audits(
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=25, le=100),
    cursor: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Audit)
        .where(Audit.org_id == principal.org_id)
        .order_by(Audit.created_at.desc())
        .limit(limit + 1)
    )
    if project_id:
        query = query.where(Audit.project_id == project_id)
    if status:
        query = query.where(Audit.status == status)
    if cursor:
        try:
            dt = datetime.fromisoformat(cursor)
            query = query.where(Audit.created_at < dt)
        except ValueError:
            pass

    result = await session.execute(query)
    audits = result.scalars().all()
    has_more = len(audits) > limit
    audits = audits[:limit]

    return {
        "items": [_format_audit(a) for a in audits],
        "next_cursor": audits[-1].created_at.isoformat() if has_more and audits else None,
    }


@router.get("/audits/{audit_id}")
async def get_audit(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()
    return _format_audit(audit)


@router.get("/audits/{audit_id}/events")
async def audit_events_sse(
    audit_id: uuid.UUID,
    last_event_id: str | None = Query(None, alias="Last-Event-ID"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """SSE stream from audit_events table. Heartbeat every 15s."""
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    settings = get_settings()
    last_id = int(last_event_id) if last_event_id else 0

    async def event_generator():  # type: ignore[return]
        nonlocal last_id
        factory = get_session_factory()
        terminal_events = {"audit_completed", "audit_failed"}

        while True:
            async with factory() as db:
                # Set RLS
                await set_rls_org(db, principal.org_id)
                result = await db.execute(
                    select(AuditEvent)
                    .where(
                        AuditEvent.audit_id == audit_id,
                        AuditEvent.id > last_id,
                    )
                    .order_by(AuditEvent.id)
                    .limit(50)
                )
                events = result.scalars().all()

            if events:
                for ev in events:
                    last_id = ev.id
                    event_type = ev.data.get("event_type", "log") if ev.data else "log"
                    data = {
                        "stage": ev.stage,
                        "level": ev.level,
                        "message": ev.message,
                        **(ev.data or {}),
                    }
                    yield f"id: {ev.id}\nevent: {event_type}\ndata: {json.dumps(data)}\n\n"

                    if event_type in terminal_events:
                        return
            else:
                # Heartbeat comment
                yield ": heartbeat\n\n"
                await asyncio.sleep(15)
                continue

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/audits/{audit_id}/cancel", status_code=202)
async def cancel_audit(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.status not in ("queued", "running"):
        raise AppError("VALIDATION_ERROR", f"Cannot cancel audit with status '{audit.status}'", 422)
    audit.cancel_requested = True
    await session.commit()
    return {"status": "cancelling"}


@router.delete("/audits/{audit_id}", status_code=204)
async def delete_audit(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Immediate purge of artifacts and source-derived data."""
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))

    from app.retention import purge_audit_data
    await purge_audit_data(session, audit)


@router.get("/audits/{audit_id}/files")
async def list_audit_files(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    result = await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )
    files = result.scalars().all()
    return {
        "items": [
            {
                "id": str(f.id),
                "path": f.path,
                "sha256": f.sha256,
                "line_count": f.line_count,
                "is_dependency": f.is_dependency,
            }
            for f in files
        ]
    }


@router.get("/audits/{audit_id}/files/{file_id}")
async def get_audit_file(
    audit_id: uuid.UUID,
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()
    if audit.status in ("queued", "running") and audit.stage in (None, "building"):
        raise AppError("AUDIT_NOT_READY", "Files not yet available", 409)

    file = await session.get(AuditFile, file_id)
    if not file or file.audit_id != audit_id:
        raise not_found("File", str(file_id))

    # Fetch content from storage
    try:
        storage = get_storage_client()
        raw_bytes = storage.get_object(file.object_key)
        content = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("file_fetch_failed", file_id=str(file_id), error=type(exc).__name__)
        raise AppError("INTERNAL", "Could not retrieve file content", 500) from exc

    return {
        "id": str(file.id),
        "path": file.path,
        "language": "solidity",
        "content": content,
    }
