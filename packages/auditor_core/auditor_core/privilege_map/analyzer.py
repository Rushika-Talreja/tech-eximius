"""
Pipeline orchestrator for Stage 2 (Analyzing) and Stage 3 (Privilege Map).
Fills:
  - contracts (semantic JSON)
  - role_nodes
  - privileged_actions
  - privilege_results
Produces PrivilegeCandidate objects for high/critical unmitigated results.
Emits privilege_map_ready event.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Audit,
    AuditFile,
    Contract as ContractDB,
    PrivilegeResult,
    PrivilegedAction as PrivilegedActionDB,
    RoleDeclaration,
    RoleNode,
)
from app.logging_config import get_logger
from auditor_core.privilege_map.roles import resolve_roles_and_actions
from auditor_core.privilege_map.scoring import (
    compute_action_score,
    compute_role_scores_with_escalation,
    get_tier,
)
from auditor_core.privilege_map.semantic import (
    ContractSemanticModel,
    build_semantic_models_for_project,
)
from auditor_core.privilege_map.templates import render_worst_case_sentence

logger = get_logger(__name__)


async def run_analyzing_stage(
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    session: AsyncSession,
    sources: dict[str, str],
    solc_version: str = "0.8.24",
) -> tuple[dict[str, ContractSemanticModel], dict[str, uuid.UUID], list[dict[str, Any]]]:
    """
    Stage 2: Analyzing.
    Builds ContractSemanticModel per contract and stores in contracts table.
    Returns: (models_map, contract_db_ids, not_analyzed_items)
    """
    models, not_analyzed = build_semantic_models_for_project(sources, solc_version=solc_version)

    # Fetch audit_files to map file path -> file_id
    file_rows = (await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )).scalars().all()
    file_ids_by_path = {f.path: f.id for f in file_rows}

    # Delete existing contracts for idempotency
    await session.execute(delete(ContractDB).where(ContractDB.audit_id == audit_id))

    contract_db_ids: dict[str, uuid.UUID] = {}

    for c_name, model in models.items():
        cid = uuid.uuid4()
        contract_db_ids[c_name] = cid

        # Find matching file_id
        file_path = model.metadata.get("spans", {}).get("file") or next(
            (f.span.file for f in model.functions), "src/Contract.sol"
        )
        file_id = file_ids_by_path.get(file_path)
        if not file_id:
            # Match by suffix
            for p, fid in file_ids_by_path.items():
                if p.endswith(file_path) or file_path.endswith(p):
                    file_id = fid
                    break
        if not file_id and file_rows:
            file_id = file_rows[0].id

        spans_meta = model.metadata.get("spans", {})
        start_line = spans_meta.get("start_line", 1)
        end_line = spans_meta.get("end_line", 100)

        contract_entry = ContractDB(
            id=cid,
            audit_id=audit_id,
            org_id=org_id,
            file_id=file_id or uuid.uuid4(),
            name=c_name,
            kind=model.kind,
            start_line=start_line,
            end_line=end_line,
            contract_type=model.contract_type,
            upgradeability=model.upgradeability,
            semantic=model.model_dump(),
        )
        session.add(contract_entry)

    await session.commit()
    logger.info("analyzing_stage_complete", contracts_count=len(models))
    return models, contract_db_ids, not_analyzed


async def run_privilege_map_stage(
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    session: AsyncSession,
    contracts: dict[str, ContractSemanticModel],
    contract_db_ids: dict[str, uuid.UUID],
) -> dict[str, Any]:
    """
    Stage 3: Privilege Map computation and persistence.
    Populates: role_nodes, privileged_actions, privilege_results.
    Produces PrivilegeCandidate objects for high/critical unmitigated results.
    """
    # Load audit_files
    file_rows = (await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit_id)
    )).scalars().all()
    file_ids_by_path = {f.path: f.id for f in file_rows}

    # Load declarations if any
    decl_rows = (await session.execute(
        select(RoleDeclaration).where(RoleDeclaration.audit_id == audit_id)
    )).scalars().all()
    declarations: dict[str, dict[str, Any]] = {
        d.role_key: {"holder_type": d.holder_type, **d.params} for d in decl_rows
    }

    # 1. Resolve roles and actions
    role_nodes_data, actions_data, missing_ac, undetected_notes = resolve_roles_and_actions(
        contracts=contracts,
        audit_id=audit_id,
        org_id=org_id,
        contract_db_ids=contract_db_ids,
        file_db_ids=file_ids_by_path,
    )

    # 2. Clean up previous results for idempotency
    await session.execute(delete(PrivilegeResult).where(PrivilegeResult.audit_id == audit_id))
    await session.execute(delete(PrivilegedActionDB).where(PrivilegedActionDB.audit_id == audit_id))
    await session.execute(delete(RoleNode).where(RoleNode.audit_id == audit_id))

    # 3. Insert RoleNodes
    for r_key, node in role_nodes_data.items():
        session.add(RoleNode(
            id=uuid.uuid4(),
            audit_id=audit_id,
            org_id=org_id,
            role_key=r_key,
            display_name=node["display_name"],
            kind=node["kind"],
            admin_role_key=node.get("admin_role_key"),
        ))

    # 4. Insert PrivilegedActions
    db_actions: list[PrivilegedActionDB] = []
    for act in actions_data:
        pa = PrivilegedActionDB(
            id=act["id"],
            audit_id=audit_id,
            org_id=org_id,
            contract_id=act["contract_id"],
            file_id=act["file_id"],
            function_signature=act["function_signature"],
            start_line=act["start_line"],
            end_line=act["end_line"],
            power_category=act["power_category"],
            guard_kind=act["guard_kind"],
            guard_roles=act["guard_roles"],
            mitigations=act["mitigations"],
            funds_impact=act["funds_impact"],
            facts=act["facts"],
        )
        session.add(pa)
        db_actions.append(pa)

    await session.flush()

    # 5. Score actions & roles
    role_action_scores: dict[str, list[int]] = {r: [] for r in role_nodes_data}
    role_breakdowns: dict[str, list[dict[str, Any]]] = {r: [] for r in role_nodes_data}
    role_actions_map: dict[str, list[PrivilegedActionDB]] = {r: [] for r in role_nodes_data}

    for action in db_actions:
        for r_key in action.guard_roles:
            decl = declarations.get(r_key)
            score, bd = compute_action_score(
                power_category=action.power_category,
                mitigations=action.mitigations,
                declaration=decl,
            )
            bd["action_id"] = str(action.id)
            role_action_scores.setdefault(r_key, []).append(score)
            role_breakdowns.setdefault(r_key, []).append(bd)
            role_actions_map.setdefault(r_key, []).append(action)

    admin_graph: dict[str, list[str]] = {}
    for r_key, node in role_nodes_data.items():
        if node.get("admin_role_key"):
            admin_graph.setdefault(node["admin_role_key"], []).append(r_key)

    role_scores = compute_role_scores_with_escalation(
        role_keys=list(role_nodes_data.keys()),
        role_action_scores=role_action_scores,
        admin_graph=admin_graph,
        declarations=declarations,
    )

    # 6. Build PrivilegeResults and PrivilegeCandidate objects
    all_candidates: list[dict[str, Any]] = []

    for r_key, node in role_nodes_data.items():
        score = role_scores.get(r_key, 0)
        tier = get_tier(score)
        decl = declarations.get(r_key)
        holder_assumed = decl is None or decl.get("holder_type") in (None, "none")

        worst_case = render_worst_case_sentence(
            role_name=node["display_name"],
            actions=role_actions_map.get(r_key, []),
            declaration=decl,
        )

        components = role_breakdowns.get(r_key, [])

        # Produce PrivilegeCandidate objects for high/critical unmitigated results
        role_candidates: list[dict[str, Any]] = []
        if tier in ("high", "critical"):
            for act in role_actions_map.get(r_key, []):
                mit = act.mitigations or {}
                has_mitigation = bool(mit.get("cap") or (mit.get("delay_seconds", 0) >= 3600))
                if not has_mitigation:
                    candidate = {
                        "role_key": r_key,
                        "power_category": act.power_category,
                        "action_id": str(act.id),
                        "contract": act.facts.get("contract_name", ""),
                        "function_signature": act.function_signature,
                        "tier": tier,
                        "blast_score": score,
                        "facts": act.facts,
                        "reason": f"Unmitigated {tier} risk: {r_key} can execute {act.power_category}",
                    }
                    role_candidates.append(candidate)
                    all_candidates.append(candidate)

        # Breakdown stored with components and candidates
        breakdown_payload = {
            "components": components,
            "candidates": role_candidates,
        }

        session.add(PrivilegeResult(
            id=uuid.uuid4(),
            audit_id=audit_id,
            org_id=org_id,
            role_key=r_key,
            blast_score=score,
            tier=tier,
            worst_case=worst_case,
            holder_assumed=holder_assumed,
            breakdown=breakdown_payload,
        ))

    await session.commit()
    logger.info("privilege_map_stage_complete", roles_count=len(role_nodes_data), actions_count=len(db_actions))

    return {
        "roles": list(role_nodes_data.keys()),
        "actions_count": len(db_actions),
        "candidates": all_candidates,
        "missing_access_control": missing_ac,
        "undetected_notes": undetected_notes,
    }

