"""
Findings endpoints:
  GET   /audits/{audit_id}/findings
  GET   /audits/{audit_id}/findings/{finding_id}
  PATCH /audits/{audit_id}/findings/{finding_id}
  GET   /audits/{audit_id}/observations  (llm_hypothesis, scored=false)
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import Audit, AuditFile, Finding, FindingEvidence, PrivilegeResult, get_db_session
from app.errors import AppError, audit_not_ready, audit_purged, not_found
from auditor_core.scoring.heuristic import compute_heuristic_scores
from auditor_schemas.constants import STANDARD_DISCLAIMER

router = APIRouter(tags=["findings"])


def _format_evidence(e: FindingEvidence) -> dict[str, Any]:
    return {
        "kind": e.kind,
        "title": e.title,
        "locator": e.locator,
        "source_url": e.source_url,
        "chunk_id": e.chunk_id,
        "quote": e.quote,
        "retrieval_score": float(e.retrieval_score) if e.retrieval_score else None,
        "facts": e.facts or {},
    }


async def _get_finding_with_evidence(
    finding_id: uuid.UUID, session: AsyncSession
) -> tuple[Finding, list[FindingEvidence]]:
    finding = await session.get(Finding, finding_id)
    if not finding:
        raise not_found("Finding", str(finding_id))

    evidence_result = await session.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id == finding_id)
    )
    evidence = evidence_result.scalars().all()
    return finding, list(evidence)


@router.get("/audits/{audit_id}/findings")
async def list_findings(
    audit_id: uuid.UUID,
    severity: str | None = None,
    source: str | None = None,
    status: str | None = None,
    scored: bool | None = None,
    limit: int = Query(default=25, le=100),
    cursor: str | None = None,
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

    file_rows = (await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )).scalars().all()
    files_by_id = {f.id: f.path for f in file_rows}

    query = select(Finding).where(Finding.audit_id == audit_id)
    if scored is not None:
        query = query.where(Finding.scored == scored)
    else:
        query = query.where(Finding.scored == True)

    if severity:
        query = query.where(Finding.severity == severity.lower())
    if source:
        query = query.where(Finding.source == source)
    if status:
        query = query.where(Finding.status == status.lower())

    query = query.order_by(Finding.created_at.desc()).limit(limit + 1)

    result = await session.execute(query)
    findings = result.scalars().all()
    has_more = len(findings) > limit
    findings = findings[:limit]

    items = []
    for f in findings:
        items.append({
            "id": str(f.id),
            "title": f.title,
            "severity": f.severity,
            "confidence": float(f.confidence),
            "source": f.source,
            "status": f.status,
            "scored": f.scored,
            "file": files_by_id.get(f.file_id),
            "start_line": f.start_line,
            "end_line": f.end_line,
            "has_patch": False,
            "proven": False,
        })

    return {
        "items": items,
        "next_cursor": findings[-1].created_at.isoformat() if has_more and findings else None,
    }


@router.get("/audits/{audit_id}/findings/{finding_id}")
async def get_finding(
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

    finding, evidence = await _get_finding_with_evidence(finding_id, session)
    if finding.audit_id != audit_id or finding.org_id != principal.org_id:
        raise not_found("Finding", str(finding_id))

    file_row = await session.get(AuditFile, finding.file_id) if finding.file_id else None

    return {
        "id": str(finding.id),
        "title": finding.title,
        "severity": finding.severity,
        "confidence": float(finding.confidence),
        "source": finding.source,
        "scored": finding.scored,
        "spans": [
            {
                "file": file_row.path if file_row else "",
                "start_line": finding.start_line or 0,
                "end_line": finding.end_line or 0,
                "sha256": file_row.sha256 if file_row else "",
            }
        ],
        "description": finding.description,
        "scenario": finding.scenario,
        "evidence": [_format_evidence(e) for e in evidence],
        "patch": None,
        "proof": None,
        "status": finding.status,
        "disclaimer": STANDARD_DISCLAIMER,
    }


class UpdateFindingRequest(BaseModel):
    status: str
    reason: str | None = None


@router.patch("/audits/{audit_id}/findings/{finding_id}")
async def update_finding(
    audit_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: UpdateFindingRequest,
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

    if body.status not in ("open", "dismissed"):
        raise AppError("VALIDATION_ERROR", "status must be 'open' or 'dismissed'", 422)

    finding.status = body.status
    session.add(finding)
    await session.flush()

    # Recompute heuristic score synchronously excluding dismissed finding
    all_findings = (await session.execute(
        select(Finding).where(Finding.audit_id == audit_id)
    )).scalars().all()
    priv_results = (await session.execute(
        select(PrivilegeResult).where(PrivilegeResult.audit_id == audit_id)
    )).scalars().all()

    scores_data = compute_heuristic_scores(all_findings, privilege_results=priv_results)
    audit.scores = scores_data
    audit.counts = scores_data.get("counts", {})
    session.add(audit)
    await session.commit()

    file_row = await session.get(AuditFile, finding.file_id) if finding.file_id else None
    evidence_res = await session.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id == finding_id)
    )
    evidences = evidence_res.scalars().all()

    return {
        "id": str(finding.id),
        "title": finding.title,
        "severity": finding.severity,
        "confidence": float(finding.confidence),
        "source": finding.source,
        "scored": finding.scored,
        "spans": [
            {
                "file": file_row.path if file_row else "",
                "start_line": finding.start_line or 0,
                "end_line": finding.end_line or 0,
                "sha256": file_row.sha256 if file_row else "",
            }
        ],
        "description": finding.description,
        "scenario": finding.scenario,
        "evidence": [_format_evidence(e) for e in evidences],
        "patch": None,
        "proof": None,
        "status": finding.status,
        "disclaimer": STANDARD_DISCLAIMER,
    }


@router.get("/audits/{audit_id}/observations")
async def list_observations(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Unscored LLM hypotheses — clearly labeled scored=false."""
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()
    if audit.status != "complete":
        raise audit_not_ready(audit.status)

    result = await session.execute(
        select(Finding).where(
            Finding.audit_id == audit_id,
            Finding.scored == False,
            Finding.source == "llm_hypothesis",
        )
    )
    observations = result.scalars().all()
    return {
        "items": [
            {
                "id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "confidence": float(f.confidence),
                "source": f.source,
                "scored": False,
                "status": f.status,
                "description": f.description,
                "disclaimer": STANDARD_DISCLAIMER,
            }
            for f in observations
        ]
    }
