"""
Privilege Map endpoints:
  GET /audits/{audit_id}/privilege-map
  PUT /audits/{audit_id}/role-declarations  (sync recompute)
  GET /audits/{audit_id}/role-declarations
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import (
    Audit,
    AuditFile,
    Contract as ContractDB,
    PrivilegeResult,
    PrivilegedAction as PrivilegedActionDB,
    RoleDeclaration,
    RoleNode,
    get_db_session,
)
from app.errors import audit_not_ready, audit_purged, not_found
from auditor_schemas.constants import STANDARD_DISCLAIMER
from auditor_schemas.models import HolderType, RoleHolderDeclaration

router = APIRouter(tags=["privilege-map"])


class DeclarationInput(BaseModel):
    role_key: str
    holder_type: str
    threshold: int | None = None
    signers: int | None = None
    delay_hours: float | None = None

    @model_validator(mode="after")
    def validate_declaration_params(self) -> "DeclarationInput":
        if self.holder_type in ("multisig", "timelock_multisig"):
            if self.threshold is not None and self.signers is not None:
                if self.threshold > self.signers:
                    raise ValueError(
                        f"threshold ({self.threshold}) must be <= signers ({self.signers})"
                    )
        if self.delay_hours is not None and self.delay_hours < 0:
            raise ValueError("delay_hours must be >= 0")
        return self


class RoleDeclarationsRequest(BaseModel):
    declarations: list[DeclarationInput]


async def _build_privilege_map_response(
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Build the privilege map JSON response from DB rows with stable deterministic ordering."""
    # Load role nodes, actions, results, declarations, audit_files, and contracts
    nodes_result = await session.execute(
        select(RoleNode).where(RoleNode.audit_id == audit_id)
    )
    nodes = {n.role_key: n for n in nodes_result.scalars().all()}

    files_result = await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )
    files = {f.id: f for f in files_result.scalars().all()}

    contracts_result = await session.execute(
        select(ContractDB).where(ContractDB.audit_id == audit_id)
    )
    contracts = {c.id: c for c in contracts_result.scalars().all()}

    actions_result = await session.execute(
        select(PrivilegedActionDB).where(PrivilegedActionDB.audit_id == audit_id)
    )
    actions_by_role: dict[str, list[PrivilegedActionDB]] = {}
    for action in actions_result.scalars().all():
        for role_key in action.guard_roles:
            actions_by_role.setdefault(role_key, []).append(action)

    results_result = await session.execute(
        select(PrivilegeResult).where(PrivilegeResult.audit_id == audit_id)
    )
    results = {r.role_key: r for r in results_result.scalars().all()}

    decl_result = await session.execute(
        select(RoleDeclaration).where(RoleDeclaration.audit_id == audit_id)
    )
    declarations = {d.role_key: d for d in decl_result.scalars().all()}

    # Collect undetected notes from contracts
    undetected_notes_set: set[str] = set()
    for c in contracts.values():
        sem = c.semantic or {}
        for note in sem.get("undetected_notes", []):
            undetected_notes_set.add(note)

    roles: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Iterate over sorted role keys for determinism
    for role_key in sorted(nodes.keys()):
        node = nodes[role_key]
        result = results.get(role_key)
        if not result:
            continue
        decl = declarations.get(role_key)
        role_actions = actions_by_role.get(role_key, [])

        # Build can_grant edges from role graph
        can_grant: list[str] = []
        for other_key in sorted(nodes.keys()):
            other_node = nodes[other_key]
            if other_node.admin_role_key == role_key:
                can_grant.append(other_key)
                edges.append({"from": role_key, "to": other_key, "kind": "can_grant"})

        # Breakdown dict or list
        if isinstance(result.breakdown, dict):
            breakdown_list = result.breakdown.get("components", [])
        elif isinstance(result.breakdown, list):
            breakdown_list = result.breakdown
        else:
            breakdown_list = []

        action_scores_by_id = {bd.get("action_id"): bd.get("score", 0) for bd in breakdown_list}

        # Build actions
        built_actions = []
        for action in role_actions:
            contract_obj = contracts.get(action.contract_id)
            contract_name = contract_obj.name if contract_obj else action.facts.get("contract_name", "")
            file_obj = files.get(action.file_id)
            file_path = file_obj.path if file_obj else ""
            file_sha256 = file_obj.sha256 if file_obj else ""

            fn_name = action.function_signature.split("(")[0]
            edges.append({
                "from": role_key,
                "to": f"{action.power_category}:{contract_name}.{fn_name}",
                "kind": "can_call",
            })

            act_score = action_scores_by_id.get(str(action.id), action.facts.get("computed_score", 0))

            built_actions.append({
                "id": str(action.id),
                "contract": contract_name,
                "function_signature": action.function_signature,
                "span": {
                    "file": file_path,
                    "start_line": action.start_line,
                    "end_line": action.end_line,
                    "sha256": file_sha256,
                },
                "power_category": action.power_category,
                "guard_kind": action.guard_kind,
                "guard_roles": sorted(action.guard_roles),
                "mitigations": action.mitigations,
                "funds_impact": action.funds_impact,
                "score": act_score,
                "facts": action.facts or {},
            })

        # Sort actions deterministically
        built_actions.sort(key=lambda a: (a["contract"], a["function_signature"], a["span"]["start_line"]))
        breakdown_list.sort(key=lambda b: str(b.get("action_id", "")))

        roles.append({
            "role_key": role_key,
            "display_name": node.display_name,
            "blast_score": result.blast_score,
            "tier": result.tier,
            "worst_case": result.worst_case,
            "holder_assumed": result.holder_assumed,
            "declaration": (
                {
                    "role_key": decl.role_key,
                    "holder_type": decl.holder_type,
                    **decl.params,
                }
                if decl
                else None
            ),
            "can_grant": sorted(can_grant),
            "actions": built_actions,
            "breakdown": breakdown_list,
        })

    # Sort edges deterministically
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))
    sorted_notes = sorted(undetected_notes_set)

    return {
        "roles": roles,
        "edges": edges,
        "undetected_notes": sorted_notes,
        "scoring_config_version": "1",
        "disclaimer": STANDARD_DISCLAIMER,
    }


@router.get("/audits/{audit_id}/privilege-map")
async def get_privilege_map(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    # 409 if privilege_map stage not complete
    completed_stages = {"privilege_map", "scanning", "retrieving", "synthesizing",
                        "patching", "verifying", "proving", "invariants", "reporting"}
    if audit.status == "complete" or audit.stage in completed_stages:
        pass
    elif audit.status in ("queued", "running"):
        raise audit_not_ready("privilege_map")

    return await _build_privilege_map_response(audit_id, principal.org_id, session)


@router.put("/audits/{audit_id}/role-declarations")
async def update_role_declarations(
    audit_id: uuid.UUID,
    body: RoleDeclarationsRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Replace full declaration set, validate, synchronously recompute scores.
    Target: < 300ms for a 2000-line project.
    """
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))
    if audit.purged_at:
        raise audit_purged()

    # Load existing role keys for validation
    nodes_result = await session.execute(
        select(RoleNode).where(RoleNode.audit_id == audit_id)
    )
    existing_roles = {n.role_key for n in nodes_result.scalars().all()}

    # Validate declarations
    validated: list[RoleHolderDeclaration] = []
    for d in body.declarations:
        if d.role_key not in existing_roles:
            from app.errors import validation_error
            raise validation_error(
                f"role_key '{d.role_key}' does not exist in this audit's privilege map"
            )
        validated.append(
            RoleHolderDeclaration(
                role_key=d.role_key,
                holder_type=HolderType(d.holder_type),
                threshold=d.threshold,
                signers=d.signers,
                delay_hours=d.delay_hours,
            )
        )

    # Delete old declarations
    await session.execute(
        delete(RoleDeclaration).where(RoleDeclaration.audit_id == audit_id)
    )

    # Insert new
    for v in validated:
        params = {}
        if v.threshold is not None:
            params["threshold"] = v.threshold
        if v.signers is not None:
            params["signers"] = v.signers
        if v.delay_hours is not None:
            params["delay_hours"] = v.delay_hours

        session.add(RoleDeclaration(
            audit_id=audit_id,
            org_id=principal.org_id,
            role_key=v.role_key,
            holder_type=v.holder_type,
            params=params,
        ))

    await session.flush()

    # Recompute scores using privilege map engine
    # (Full recompute — synchronous for small projects)
    from auditor_core.privilege_map.scoring import recompute_scores
    await recompute_scores(audit_id, principal.org_id, session)

    await session.commit()

    return await _build_privilege_map_response(audit_id, principal.org_id, session)


@router.get("/audits/{audit_id}/role-declarations")
async def get_role_declarations(
    audit_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    audit = await session.get(Audit, audit_id)
    if not audit or audit.org_id != principal.org_id:
        raise not_found("Audit", str(audit_id))

    result = await session.execute(
        select(RoleDeclaration).where(RoleDeclaration.audit_id == audit_id)
    )
    declarations = result.scalars().all()
    return {
        "declarations": [
            {
                "role_key": d.role_key,
                "holder_type": d.holder_type,
                **d.params,
            }
            for d in declarations
        ]
    }
