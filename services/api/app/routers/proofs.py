"""
Proofs endpoints for Milestone 6 (F5 / Stage 9).
Behind feature flag PROOFS_ENABLED.
Endpoints:
  POST /audits/{audit_id}/findings/{finding_id}/proof (202, rate-limited)
  GET  /findings/{finding_id}/proof (200)
  GET  /audits/{audit_id}/findings/{finding_id}/proof (200)
  GET  /audits/{audit_id}/proofs (200)
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from auditor_core.patching.service import generate_and_verify_patch
from auditor_core.patching.verifier import apply_unified_diff
from auditor_core.proofs.drafter import draft_proof_test, is_detector_supported
from auditor_core.proofs.verifier import verify_proof_test
from auditor_schemas.constants import STANDARD_DISCLAIMER
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.config import get_settings
from app.db import (
    Audit,
    AuditFile,
    Finding,
    FindingEvidence,
    Patch,
    Proof,
    get_db_session,
)
from app.errors import (
    AppError,
    audit_purged,
    feature_disabled,
    not_found,
    validation_error,
)
from app.rate_limiter import rate_limit
from app.storage import get_storage_client

router = APIRouter(tags=["proofs"])

# Dedicated rate limiter for exploit proofs: max 10 requests per minute
proof_rate_limiter = rate_limit(limit=10, window_seconds=60)


def _format_proof(p: Proof) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "finding_id": str(p.finding_id),
        "test_source": p.test_source,
        "fails_on_original": p.fails_on_original,
        "passes_on_patched": p.passes_on_patched,
        "run_log": p.run_log or [],
        "disclaimer": STANDARD_DISCLAIMER,
    }


@router.post(
    "/audits/{audit_id}/findings/{finding_id}/proof",
    status_code=202,
    dependencies=[Depends(proof_rate_limiter)],
)
async def generate_proof(
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.proofs_enabled:
        raise feature_disabled("proofs")

    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    finding = await session.get(Finding, finding_id)
    if not finding or finding.audit_id != audit_id or finding.org_id != principal.org_id:
        raise not_found("Finding", str(finding_id))

    # Supported detectors check
    supported, vuln_category = is_detector_supported(
        detector_name=finding.source,
        title=finding.title,
        description=finding.description or "",
    )
    if not supported:
        raise validation_error(
            f"Detector class for finding '{finding.title}' is not supported for exploit proofs. "
            "Supported classes: reentrancy, missing access control, "
            "unchecked call, simple oracle read."
        )

    # Load source files
    storage = get_storage_client()
    files_result = await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )
    file_rows = files_result.scalars().all()
    original_sources: dict[str, str] = {}
    for f in file_rows:
        try:
            original_sources[f.path] = storage.get_object(f.object_key).decode("utf-8")
        except Exception:
            original_sources[f.path] = ""

    # Find or verify patch
    patch_result = await session.execute(
        select(Patch)
        .where(Patch.finding_id == finding_id, Patch.status == "verified")
        .order_by(Patch.version.desc())
        .limit(1)
    )
    verified_patch = patch_result.scalars().first()

    target_file_path = ""
    if finding.file_id:
        for f in file_rows:
            if f.id == finding.file_id:
                target_file_path = f.path
                target_source = original_sources.get(f.path, "")
                break
    if not target_source and original_sources:
        target_file_path = list(original_sources.keys())[0]
        target_source = list(original_sources.values())[0]

    patched_sources: dict[str, str] = {}
    if verified_patch and verified_patch.unified_diff:
        try:
            patched_sources = apply_unified_diff(original_sources, verified_patch.unified_diff)
        except Exception:
            patched_sources = original_sources
    else:
        # Generate patch if needed
        p_res = await generate_and_verify_patch(
            sources=original_sources,
            target_finding={
                "title": finding.title,
                "description": finding.description or "",
                "file_path": target_file_path,
                "detector": finding.source,
            },
            original_findings=[],
            solc_version=audit.compiler_version or "0.8.24",
            patch_mode=settings.patch_mode,
        )
        if p_res.get("status") == "verified" and p_res.get("unified_diff"):
            try:
                patched_sources = apply_unified_diff(original_sources, p_res["unified_diff"])
            except Exception:
                patched_sources = original_sources
        else:
            patched_sources = original_sources

    # Determine contract source and name
    contract_name = Path(target_file_path).stem if target_file_path else "TargetContract"

    # Draft Foundry test
    try:
        draft = await draft_proof_test(
            contract_name=contract_name,
            original_source=target_source,
            finding_title=finding.title,
            finding_detector=finding.source,
            finding_description=finding.description or "",
        )
    except Exception as exc:
        raise validation_error(f"Failed to draft exploit proof test: {exc}")

    # Verify test in sandbox-test
    verif_res = verify_proof_test(
        test_source=draft.test_source,
        original_sources=original_sources,
        patched_sources=patched_sources,
        solc_version=audit.compiler_version or "0.8.24",
        sandbox_runtime=settings.sandbox_runtime,
    )

    if not verif_res.accepted:
        raise AppError(
            "VALIDATION_ERROR",
            verif_res.rejection_reason or "Proof verification rejected",
            422,
            {"run_log": verif_res.run_log},
        )

    # Store accepted Proof
    proof = Proof(
        finding_id=finding_id,
        org_id=principal.org_id,
        test_source=draft.test_source,
        fails_on_original=True,
        passes_on_patched=True,
        run_log=verif_res.run_log,
    )
    session.add(proof)

    # Add proof evidence to finding
    proof_evidence = FindingEvidence(
        finding_id=finding_id,
        org_id=principal.org_id,
        kind="proof",
        title=f"Exploit Test Proof: {finding.title}",
        locator=f"Proof #{proof.id}",
        facts={
            "proof_id": str(proof.id),
            "fails_on_original": True,
            "passes_on_patched": True,
            "attacker_gain_rule": draft.attacker_gain_rule,
        },
    )
    session.add(proof_evidence)

    # Raise confidence on finding
    current_conf = float(finding.confidence)
    finding.confidence = min(1.0, current_conf + 0.15)
    await session.commit()

    return {"proof_id": str(proof.id), "status": "verified"}


@router.get("/findings/{finding_id}/proof")
async def get_proof_by_finding(
    finding_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.proofs_enabled:
        raise feature_disabled("proofs")

    proof_res = await session.execute(
        select(Proof)
        .where(Proof.finding_id == finding_id, Proof.org_id == principal.org_id)
        .order_by(Proof.created_at.desc())
        .limit(1)
    )
    proof = proof_res.scalars().first()
    if not proof:
        raise not_found("Proof for finding", str(finding_id))

    return _format_proof(proof)


@router.get("/audits/{audit_id}/findings/{finding_id}/proof")
async def get_audit_finding_proof(
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    return await get_proof_by_finding(finding_id=finding_id, principal=principal, session=session)


@router.get("/audits/{audit_id}/proofs")
async def list_audit_proofs(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.proofs_enabled:
        raise feature_disabled("proofs")

    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    # Find all findings for audit
    findings_res = await session.execute(
        select(Finding.id).where(Finding.audit_id == audit_id, Finding.org_id == principal.org_id)
    )
    finding_ids = findings_res.scalars().all()
    if not finding_ids:
        return {"items": []}

    proofs_res = await session.execute(
        select(Proof).where(Proof.finding_id.in_(finding_ids), Proof.org_id == principal.org_id)
    )
    proofs = proofs_res.scalars().all()
    return {"items": [_format_proof(p) for p in proofs]}
