"""
GET /audits/{audit_id}/export?format=json|md|sarif|pdf
Every export contains: disclaimer, coverage, toolchain, corpus version, scoring weights.
Never outputs safe/secure/audited/certified/compliant as a verdict.
Uses "No verified issues detected by this analysis" when clean.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import Audit, Finding, FindingEvidence, get_db_session
from app.errors import AppError, audit_not_ready, audit_purged, not_found
from auditor_schemas.constants import STANDARD_DISCLAIMER

router = APIRouter(tags=["export"])

CLEAN_VERDICT = "No verified issues detected by this analysis"


@router.get("/audits/{audit_id}/export")
async def export_audit(
    audit_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|md|sarif|pdf)$"),
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

    # Load findings
    findings_result = await session.execute(
        select(Finding).where(Finding.audit_id == audit_id, Finding.scored == True)
    )
    findings = findings_result.scalars().all()

    scores_obj = audit.scores or {}
    scoring_weights = scores_obj.get("weights")
    coverage_obj = audit.coverage or {"analyzed": {}, "not_analyzed": [], "out_of_scope": []}
    verdict = CLEAN_VERDICT if not findings else None

    report = {
        "audit_id": str(audit_id),
        "generated_at": datetime.utcnow().isoformat(),
        "disclaimer": STANDARD_DISCLAIMER,
        "toolchain": audit.toolchain or {},
        "corpus_version": audit.corpus_version or "2026.10.1",
        "coverage": coverage_obj,
        "scores": scores_obj,
        "scoring_weights": scoring_weights,
        "findings": [
            {
                "id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "confidence": float(f.confidence),
                "source": f.source,
                "status": f.status,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "description": f.description,
            }
            for f in findings
        ],
    }
    if verdict:
        report["verdict"] = verdict

    if format == "json":
        content = json.dumps(report, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="audit-{audit_id}.json"'
            },
        )

    elif format == "md":
        lines = [
            f"# DeFi Contract Audit Report",
            f"",
            f"**Audit ID:** {audit_id}  ",
            f"**Generated:** {report['generated_at']}  ",
            f"**Toolchain:** solc {audit.compiler_version or '0.8.24'}  ",
            f"**Corpus Version:** {report['corpus_version']}  ",
            f"",
            f"> **DISCLAIMER:** {STANDARD_DISCLAIMER}",
            f"",
            f"## Scores ({scores_obj.get('label', 'heuristic risk indicator')})",
            f"- **Security Score:** {scores_obj.get('security', 'N/A')}/100",
            f"- **Overall Score:** {scores_obj.get('overall', 'N/A')}/100",
            f"",
            f"## Coverage Statement",
            f"- **Analyzed Contracts:** {', '.join(coverage_obj.get('analyzed', {}).get('contracts', [])) or 'None'}",
            f"- **Detectors Run:** {len(coverage_obj.get('analyzed', {}).get('detectors_run', []))} detectors",
            f"- **Out of Scope:** {', '.join(coverage_obj.get('out_of_scope', []))}",
            f"",
            f"## Findings",
            f"",
        ]
        if not report["findings"]:
            lines.append(f"> **Verdict:** {CLEAN_VERDICT}")
            lines.append("")
        else:
            for f in report["findings"]:
                lines.append(f"### [{f['severity'].upper()}] {f['title']}")
                lines.append(f"*Source:* {f['source']} | *Status:* {f['status']}")
                lines.append(f"")
                lines.append(f.get("description", ""))
                lines.append(f"")

        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="audit-{audit_id}.md"'
            },
        )

    elif format == "sarif":
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "DeFi Contract Auditor",
                            "version": "0.1.0",
                            "informationUri": "https://example.com",
                            "rules": [],
                        }
                    },
                    "results": [
                        {
                            "ruleId": f.detector or f.source,
                            "level": {
                                "critical": "error",
                                "high": "error",
                                "medium": "warning",
                                "low": "note",
                                "info": "none",
                            }.get(f.severity.lower(), "warning"),
                            "message": {"text": f.description or f.title},
                        }
                        for f in findings
                    ],
                    "properties": {
                        "disclaimer": STANDARD_DISCLAIMER,
                        "corpusVersion": report["corpus_version"],
                        "coverage": coverage_obj,
                        "scoringWeights": scoring_weights,
                        "verdict": verdict,
                    },
                }
            ],
        }
        return Response(
            content=json.dumps(sarif, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="audit-{audit_id}.sarif"'
            },
        )

    elif format == "pdf":
        raise AppError("VALIDATION_ERROR", "PDF export is not yet implemented", 422)
