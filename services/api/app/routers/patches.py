"""
Patches endpoints for Milestone 5 (F8 / Stages 7 & 8).
Endpoints:
  POST /audits/{audit_id}/findings/{finding_id}/patches (202)
  GET  /audits/{audit_id}/findings/{finding_id}/patches (200)
  GET  /patches/{patch_id} (200)
  POST /patches/{patch_id}/verify (202)
Patches are offered only when status=verified.
Emits patch_ready events.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from auditor_core.patching.service import generate_and_verify_patch
from auditor_core.patching.verifier import verify_patch
from auditor_schemas.constants import STANDARD_DISCLAIMER
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.config import get_settings
from app.db import (
    Audit,
    AuditEvent,
    AuditFile,
    Finding,
    FindingEvidence,
    Patch,
    get_db_session,
    get_session_factory,
)
from app.errors import audit_not_ready, audit_purged, not_found
from app.storage import get_storage_client

router = APIRouter(tags=["patches"])


class VerifyPatchRequest(BaseModel):
    unified_diff: str = Field(description="User-edited unified diff to verify")


def _format_patch(p: Patch) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "finding_id": str(p.finding_id),
        "version": p.version,
        "status": p.status,
        "unified_diff": p.unified_diff,
        "rationale": p.rationale,
        "compiles": p.compiles,
        "finding_cleared": p.finding_cleared,
        "new_findings": p.new_findings or [],
        "tests_passed": p.tests_passed,
        "gas_delta": p.gas_delta or {},
        "verification_log": p.verification_log or [],
        "disclaimer": STANDARD_DISCLAIMER,
    }


async def _run_patch_generation_pipeline(
    patch_id: uuid.UUID,
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    org_id: uuid.UUID,
    patch_mode: str,
) -> None:
    session_factory = get_session_factory()
    storage = get_storage_client()

    async with session_factory() as session:
        patch = await session.get(Patch, patch_id)
        finding = await session.get(Finding, finding_id)
        audit = await session.get(Audit, audit_id)
        if not patch or not finding or not audit:
            return

        # Fetch audit files
        files_result = await session.execute(
            select(AuditFile).where(AuditFile.audit_id == audit_id)
        )
        file_rows = files_result.scalars().all()
        sources: dict[str, str] = {}
        for f in file_rows:
            try:
                sources[f.path] = storage.get_object(f.object_key).decode("utf-8")
            except Exception:
                sources[f.path] = ""

        # Fetch finding evidence for remediation text
        ev_res = await session.execute(
            select(FindingEvidence).where(FindingEvidence.finding_id == finding_id)
        )
        ev_rows = ev_res.scalars().all()
        remediation_text = " ".join([e.quote or "" for e in ev_rows if e.quote])

        # Fetch original findings
        all_f_res = await session.execute(
            select(Finding).where(Finding.audit_id == audit_id)
        )
        all_findings = all_f_res.scalars().all()
        file_map = {f.id: f.path for f in file_rows}
        orig_findings = [
            {
                "detector": f.detector,
                "title": f.title,
                "severity": f.severity,
                "file_path": file_map.get(f.file_id, ""),
                "start_line": f.start_line,
                "function_signature": None,
            }
            for f in all_findings
        ]

        target_finding_dict = {
            "title": finding.title,
            "detector": finding.detector,
            "severity": finding.severity,
            "file_path": file_map.get(finding.file_id, ""),
            "start_line": finding.start_line or 1,
            "end_line": finding.end_line or (finding.start_line or 1),
            "description": finding.description,
        }

        solc_version = audit.compiler_version or "0.8.24"

        # Run patch generation + verification
        result = await generate_and_verify_patch(
            sources=sources,
            target_finding=target_finding_dict,
            original_findings=orig_findings,
            solc_version=solc_version,
            remediation_text=remediation_text,
            patch_mode=patch_mode,
        )

        patch.status = result["status"]
        patch.unified_diff = result["unified_diff"]
        patch.rationale = result["rationale"]
        patch.compiles = result["compiles"]
        patch.finding_cleared = result["finding_cleared"]
        patch.new_findings = result["new_findings"]
        patch.gas_delta = result["gas_delta"]
        patch.verification_log = result["verification_log"]

        # Emit patch_ready event
        event = AuditEvent(
            audit_id=audit_id,
            org_id=org_id,
            stage="patching",
            level="info",
            message=f"Patch {patch.id} {result['status']}",
            data={
                "event_type": "patch_ready",
                "patch_id": str(patch.id),
                "finding_id": str(finding_id),
                "status": result["status"],
                "version": patch.version,
            },
        )
        session.add(event)
        await session.commit()


async def _run_verify_pipeline(
    patch_id: uuid.UUID,
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    org_id: uuid.UUID,
    edited_diff: str,
) -> None:
    session_factory = get_session_factory()
    storage = get_storage_client()

    async with session_factory() as session:
        patch = await session.get(Patch, patch_id)
        finding = await session.get(Finding, finding_id)
        audit = await session.get(Audit, audit_id)
        if not patch or not finding or not audit:
            return

        files_result = await session.execute(
            select(AuditFile).where(AuditFile.audit_id == audit_id)
        )
        file_rows = files_result.scalars().all()
        sources: dict[str, str] = {}
        for f in file_rows:
            try:
                sources[f.path] = storage.get_object(f.object_key).decode("utf-8")
            except Exception:
                sources[f.path] = ""

        all_f_res = await session.execute(
            select(Finding).where(Finding.audit_id == audit_id)
        )
        all_findings = all_f_res.scalars().all()
        file_map = {f.id: f.path for f in file_rows}
        orig_findings = [
            {
                "detector": f.detector,
                "title": f.title,
                "severity": f.severity,
                "file_path": file_map.get(f.file_id, ""),
                "start_line": f.start_line,
                "function_signature": None,
            }
            for f in all_findings
        ]

        target_finding_dict = {
            "title": finding.title,
            "detector": finding.detector,
            "severity": finding.severity,
            "file_path": file_map.get(finding.file_id, ""),
            "start_line": finding.start_line or 1,
            "end_line": finding.end_line or (finding.start_line or 1),
            "description": finding.description,
        }

        solc_version = audit.compiler_version or "0.8.24"

        v_res = await verify_patch(
            project_sources=sources,
            unified_diff=edited_diff,
            target_finding=target_finding_dict,
            original_findings=orig_findings,
            solc_version=solc_version,
        )

        patch.status = "verified" if v_res.ok else "rejected"
        patch.compiles = v_res.compiles
        patch.finding_cleared = v_res.finding_cleared
        patch.new_findings = v_res.new_findings
        patch.gas_delta = v_res.gas_delta
        patch.verification_log = v_res.log

        event = AuditEvent(
            audit_id=audit_id,
            org_id=org_id,
            stage="patching",
            level="info",
            message=f"Patch {patch.id} {patch.status}",
            data={
                "event_type": "patch_ready",
                "patch_id": str(patch.id),
                "finding_id": str(finding_id),
                "status": patch.status,
                "version": patch.version,
            },
        )
        session.add(event)
        await session.commit()


@router.post("/audits/{audit_id}/findings/{finding_id}/patches", status_code=202)
async def generate_patch(
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()
    if audit.status != "complete":
        raise audit_not_ready(audit.status)

    finding = await session.get(Finding, finding_id)
    if not finding or finding.audit_id != audit_id or finding.org_id != principal.org_id:
        raise not_found("Finding", str(finding_id))

    settings = get_settings()

    patch = Patch(
        id=uuid.uuid4(),
        finding_id=finding_id,
        org_id=principal.org_id,
        version=1,
        unified_diff="",
        rationale="Patch generation in progress...",
        status="draft",
        created_at=datetime.utcnow(),
    )
    session.add(patch)
    await session.commit()

    # Launch background task
    asyncio.create_task(
        _run_patch_generation_pipeline(
            patch.id,
            audit_id,
            finding_id,
            principal.org_id,
            settings.patch_mode,
        )
    )

    return {
        "id": str(patch.id),
        "patch_id": str(patch.id),
        "version": patch.version,
        "status": patch.status,
    }


@router.get("/audits/{audit_id}/findings/{finding_id}/patches")
async def list_patches(
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    finding = await session.get(Finding, finding_id)
    if not finding or finding.audit_id != audit_id or finding.org_id != principal.org_id:
        raise not_found("Finding", str(finding_id))

    result = await session.execute(
        select(Patch)
        .where(Patch.finding_id == finding_id, Patch.org_id == principal.org_id)
        .order_by(Patch.version.desc())
    )
    patches = result.scalars().all()

    return {"items": [_format_patch(p) for p in patches]}


@router.get("/patches/{patch_id}")
async def get_patch(
    patch_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    patch = await session.get(Patch, patch_id)
    if not patch or patch.org_id != principal.org_id:
        raise not_found("Patch", str(patch_id))

    return _format_patch(patch)


@router.post("/patches/{patch_id}/verify", status_code=202)
async def verify_patch_endpoint(
    patch_id: uuid.UUID,
    body: VerifyPatchRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    existing_patch = await session.get(Patch, patch_id)
    if not existing_patch or existing_patch.org_id != principal.org_id:
        raise not_found("Patch", str(patch_id))

    finding = await session.get(Finding, existing_patch.finding_id)
    if not finding or finding.org_id != principal.org_id:
        raise not_found("Finding", str(existing_patch.finding_id))

    new_version = existing_patch.version + 1

    new_patch = Patch(
        id=uuid.uuid4(),
        finding_id=finding.id,
        org_id=principal.org_id,
        version=new_version,
        unified_diff=body.unified_diff,
        rationale=f"User-edited patch (version {new_version})",
        status="draft",
        created_at=datetime.utcnow(),
    )
    session.add(new_patch)
    await session.commit()

    asyncio.create_task(
        _run_verify_pipeline(
            new_patch.id,
            finding.audit_id,
            finding.id,
            principal.org_id,
            body.unified_diff,
        )
    )

    return {
        "id": str(new_patch.id),
        "patch_id": str(new_patch.id),
        "version": new_patch.version,
        "status": new_patch.status,
    }
