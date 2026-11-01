"""
Invariants endpoints for Milestone 7 (F6 / Stage 10).
Behind feature flag INVARIANTS_ENABLED.
Endpoints:
  POST /audits/{audit_id}/invariant-runs (202)
  GET  /audits/{audit_id}/invariant-runs (200)
  GET  /audits/{audit_id}/invariants (200)
"""
from __future__ import annotations

import uuid
from typing import Any

from auditor_core.invariants.runner import run_invariant_suite_for_contract
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.config import get_settings
from app.db import (
    Audit,
    AuditFile,
    Contract,
    Finding,
    FindingEvidence,
    InvariantRun,
    get_db_session,
)
from app.errors import (
    audit_purged,
    feature_disabled,
    not_found,
    validation_error,
)
from app.storage import get_storage_client

router = APIRouter(tags=["invariants"])


class CreateInvariantRunRequest(BaseModel):
    contract_id: uuid.UUID | None = None
    contract_type_override: str | None = None
    templates: list[str] = Field(default_factory=lambda: ["all"])


def _format_invariant_run(run: InvariantRun, contract_name: str = "") -> dict[str, Any]:
    run_log = run.run_log or []
    reason = None
    desc = run.template_id
    for entry in run_log:
        if isinstance(entry, dict) and entry.get("reason"):
            reason = entry["reason"]
            break

    return {
        "id": str(run.id),
        "contract": contract_name,
        "contract_id": str(run.contract_id),
        "template_id": run.template_id,
        "description": desc,
        "status": run.status,
        "reason": reason,
        "counterexample": run.counterexample,
        "run_log": run_log,
    }


@router.post("/audits/{audit_id}/invariant-runs", status_code=202)
async def start_invariant_run(
    audit_id: uuid.UUID,
    body: CreateInvariantRunRequest = CreateInvariantRunRequest(),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.invariants_enabled:
        raise feature_disabled("invariants")

    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    # Load contracts
    if body.contract_id:
        contract_res = await session.execute(
            select(Contract).where(Contract.id == body.contract_id, Contract.audit_id == audit_id)
        )
        contracts = contract_res.scalars().all()
        if not contracts:
            raise not_found("Contract", str(body.contract_id))
    else:
        contract_res = await session.execute(
            select(Contract).where(Contract.audit_id == audit_id, Contract.kind.in_(["contract"]))
        )
        contracts = contract_res.scalars().all()

    if not contracts:
        raise validation_error("No contracts found to execute invariants against")

    # Load source files
    storage = get_storage_client()
    files_result = await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )
    file_rows = {f.id: f for f in files_result.scalars().all()}

    run_group_id = uuid.uuid4()
    recorded_runs: list[InvariantRun] = []

    for c in contracts:
        file_row = file_rows.get(c.file_id)
        source_code = ""
        if file_row:
            try:
                source_code = storage.get_object(file_row.object_key).decode("utf-8")
            except Exception:
                source_code = ""

        # Extract function names and inheritance from semantic
        semantic_data = c.semantic or {}
        fn_names = {f.get("name") for f in semantic_data.get("functions", []) if f.get("name")}
        inheritance = semantic_data.get("inheritance", [])

        c_type, confidence, results = run_invariant_suite_for_contract(
            contract_name=c.name,
            contract_source=source_code,
            function_names=fn_names,
            inheritance=inheritance,
            override_type=body.contract_type_override,
            requested_templates=body.templates,
            solc_version=audit.compiler_version or "0.8.24",
        )

        for res in results:
            run_log = list(res.run_log)
            if res.reason:
                run_log.append({"reason": res.reason})

            inv_run = InvariantRun(
                audit_id=audit_id,
                org_id=principal.org_id,
                contract_id=c.id,
                template_id=res.template_id,
                status=res.status,
                counterexample=res.counterexample,
                run_log=run_log,
            )
            session.add(inv_run)
            recorded_runs.append(inv_run)

            # If violated: create finding with proof evidence
            if res.status == "violated":
                finding_id = uuid.uuid4()
                inv_finding = Finding(
                    id=finding_id,
                    audit_id=audit_id,
                    org_id=principal.org_id,
                    file_id=c.file_id,
                    source="invariant",
                    detector=res.template_id,
                    title=f"Invariant Violation: {res.template_id} ({res.description})",
                    severity="high",
                    confidence=1.0,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    description=(
                        f"Invariant '{res.description}' was violated on contract {c.name}. "
                        f"Reason: {res.reason or 'Property violated during bounded test'}."
                    ),
                    scenario=f"Counterexample call sequence: {res.counterexample}",
                    status="open",
                    scored=True,
                )
                session.add(inv_finding)

                evidence = FindingEvidence(
                    finding_id=finding_id,
                    org_id=principal.org_id,
                    kind="proof",
                    title=f"Invariant Counterexample: {res.template_id}",
                    locator=f"{file_row.path if file_row else c.name}:{c.start_line}",
                    facts={
                        "template_id": res.template_id,
                        "counterexample": res.counterexample,
                        "contract": c.name,
                    },
                )
                session.add(evidence)

    await session.commit()
    return {"run_group_id": str(run_group_id), "runs_count": len(recorded_runs)}


@router.get("/audits/{audit_id}/invariant-runs")
async def list_invariant_runs(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.invariants_enabled:
        raise feature_disabled("invariants")

    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    # Load contract names
    contracts_res = await session.execute(
        select(Contract).where(Contract.audit_id == audit_id)
    )
    contract_names = {c.id: c.name for c in contracts_res.scalars().all()}

    runs_res = await session.execute(
        select(InvariantRun)
        .where(InvariantRun.audit_id == audit_id, InvariantRun.org_id == principal.org_id)
        .order_by(InvariantRun.created_at.desc())
    )
    runs = runs_res.scalars().all()

    return {
        "items": [
            _format_invariant_run(r, contract_names.get(r.contract_id, "UnknownContract"))
            for r in runs
        ]
    }


@router.get("/audits/{audit_id}/invariants")
async def list_invariants_alias(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """Alias for tester frontend compatibility."""
    return await list_invariant_runs(audit_id=audit_id, principal=principal, session=session)
