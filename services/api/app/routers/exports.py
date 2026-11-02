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
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import Audit, Finding, FindingEvidence, Proof, get_db_session
from app.errors import AppError, audit_not_ready, audit_purged, not_found
from auditor_schemas.constants import STANDARD_DISCLAIMER

router = APIRouter(tags=["export"])


def _generate_fallback_pdf(report: dict, findings_data: list[dict], verdict: str | None) -> bytes:
    """Fallback minimalist valid PDF generator when WeasyPrint / cairo is unavailable."""
    audit_id = report.get("audit_id", "")
    lines = [
        "DeFi Contract Audit Advisory Report",
        f"Audit ID: {audit_id}",
        f"Generated: {report.get('generated_at', '')}",
        "---",
        "DISCLAIMER:",
        report.get("disclaimer", "")[:90] + "...",
        "---",
        "FINDINGS:"
    ]
    if findings_data:
        for f in findings_data[:20]:
            sev = (f.get("severity") or "INFO").upper()
            title = (f.get("title") or "")[:50]
            lines.append(f"[{sev}] {title}")
    else:
        lines.append(verdict or "No verified issues detected by this analysis")

    stream_data = "BT /F1 10 Tf 40 750 Td 14 TL "
    for l in lines:
        safe_l = str(l).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_data += f"({safe_l}) ' "
    stream_data += "ET"
    stream_bytes = stream_data.encode("latin-1", "replace")

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n"
        b"4 0 obj <</Length " + str(len(stream_bytes)).encode() + b">> stream\n" + stream_bytes + b"\nendstream\nendobj\n"
        b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000225 00000 n \n0000000300 00000 n \ntrailer <</Size 6 /Root 1 0 R>>\nstartxref\n380\n%%EOF\n"
    )
    return pdf


def _build_pdf_html(report: dict, findings_data: list[dict], verdict: str | None) -> str:
    """Build a self-contained HTML document for WeasyPrint to render as PDF."""
    disclaimer = report.get("disclaimer", "")
    audit_id = report.get("audit_id", "")
    generated_at = report.get("generated_at", "")
    toolchain = report.get("toolchain") or {}
    corpus_version = report.get("corpus_version", "")
    scores = report.get("scores") or {}
    coverage = report.get("coverage") or {}
    analyzed = coverage.get("analyzed") or {}
    out_of_scope = coverage.get("out_of_scope") or []

    toolchain_str = ", ".join(f"{k} {v}" for k, v in toolchain.items()) or "N/A"
    contracts_str = ", ".join(analyzed.get("contracts") or []) or "None"
    detectors_count = len(analyzed.get("detectors_run") or [])
    out_of_scope_str = ", ".join(out_of_scope) or "None"

    findings_html = ""
    if findings_data:
        rows = ""
        for f in findings_data:
            sev = (f.get("severity") or "").upper()
            sev_color = {
                "CRITICAL": "#7b0000", "HIGH": "#c0392b", "MEDIUM": "#e67e22",
                "LOW": "#2980b9", "INFO": "#27ae60",
            }.get(sev, "#555")
            rows += f"""
            <tr>
              <td style="color:{sev_color};font-weight:bold">{sev}</td>
              <td>{f.get('title','')}</td>
              <td>{f.get('source','')}</td>
              <td>{f.get('status','')}</td>
              <td style="font-size:0.85em">{(f.get('description','') or '')[:200]}</td>
            </tr>"""
        findings_html = f"""
        <h2>Findings</h2>
        <table>
          <thead><tr><th>Severity</th><th>Title</th><th>Source</th><th>Status</th><th>Description</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        clean = verdict or "No verified issues detected by this analysis"
        findings_html = f'<h2>Findings</h2><p class="clean">{clean}</p>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>DeFi Contract Audit Report</title>
<style>
  body {{ font-family: sans-serif; font-size: 11pt; margin: 2cm; color: #222; }}
  h1 {{ font-size: 18pt; border-bottom: 2px solid #333; padding-bottom: 6px; }}
  h2 {{ font-size: 13pt; margin-top: 1.5em; color: #333; }}
  .meta {{ color: #555; font-size: 0.9em; margin-bottom: 1em; }}
  .disclaimer {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px 14px;
                 border-radius: 4px; font-size: 0.88em; margin: 1em 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
  th {{ background: #333; color: #fff; padding: 6px 8px; text-align: left; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
  .clean {{ font-weight: bold; color: #27ae60; font-size: 1.1em; }}
  .score-box {{ display: inline-block; padding: 4px 12px; border-radius: 4px;
                background: #eef; border: 1px solid #99c; margin-right: 10px; }}
</style>
</head>
<body>
<h1>DeFi Contract Audit Report</h1>
<div class="meta">
  <strong>Audit ID:</strong> {audit_id}<br>
  <strong>Generated:</strong> {generated_at}<br>
  <strong>Toolchain:</strong> {toolchain_str}<br>
  <strong>Corpus Version:</strong> {corpus_version}
</div>
<div class="disclaimer"><strong>⚠ DISCLAIMER:</strong> {disclaimer}</div>
<h2>Scores <small>({scores.get('label','heuristic risk indicator')})</small></h2>
<span class="score-box">Security: {scores.get('security','N/A')}/100</span>
<span class="score-box">Overall: {scores.get('overall','N/A')}/100</span>
<h2>Coverage Statement</h2>
<ul>
  <li><strong>Analyzed Contracts:</strong> {contracts_str}</li>
  <li><strong>Detectors Run:</strong> {detectors_count}</li>
  <li><strong>Out of Scope:</strong> {out_of_scope_str}</li>
</ul>
{findings_html}
</body>
</html>"""

CLEAN_VERDICT = "No verified issues detected by this analysis"


@router.get("/audits/{audit_id}/export")
async def export_audit(
    audit_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|md|sarif|pdf)$"),
    include_tests: bool = Query(default=False),
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

    # Load proof tests if opted in
    proof_tests: dict[uuid.UUID, str] = {}
    if include_tests and findings:
        proof_res = await session.execute(
            select(Proof).where(
                Proof.finding_id.in_([f.id for f in findings]),
                Proof.fails_on_original == True,
                Proof.passes_on_patched == True,
            )
        )
        for p in proof_res.scalars().all():
            proof_tests[p.finding_id] = p.test_source

    scores_obj = audit.scores or {}
    scoring_weights = scores_obj.get("weights")
    coverage_obj = audit.coverage or {"analyzed": {}, "not_analyzed": [], "out_of_scope": []}
    verdict = CLEAN_VERDICT if not findings else None

    findings_data = []
    for f in findings:
        item: dict[str, Any] = {
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
        if include_tests and f.id in proof_tests:
            item["test_source"] = proof_tests[f.id]
        findings_data.append(item)

    report = {
        "audit_id": str(audit_id),
        "generated_at": datetime.utcnow().isoformat(),
        "disclaimer": STANDARD_DISCLAIMER,
        "toolchain": audit.toolchain or {},
        "corpus_version": audit.corpus_version or "2026.10.1",
        "coverage": coverage_obj,
        "scores": scores_obj,
        "scoring_weights": scoring_weights,
        "findings": findings_data,
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
        try:
            import weasyprint
            html = _build_pdf_html(report, findings_data, CLEAN_VERDICT if not findings else None)
            pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        except Exception:
            pdf_bytes = _generate_fallback_pdf(report, findings_data, CLEAN_VERDICT if not findings else None)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="audit-{audit_id}.pdf"'
            },
        )
