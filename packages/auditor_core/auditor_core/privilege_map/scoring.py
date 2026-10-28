"""
Privilege Map scoring engine.
Loads weights and base scores from scoring_config.yaml.
Calculates action scores, role scores with escalation, tiers, and per-action breakdowns.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any
import uuid

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

CONFIG_PATH = Path(__file__).parent / "scoring_config.yaml"


def load_scoring_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


SCORING_CONFIG = load_scoring_config()


def get_delay_multiplier(delay_seconds: float) -> float:
    """Delay multiplier: >=24h -> 0.5, >=1h -> 0.75, else 1.0."""
    if delay_seconds >= 86400:
        return float(SCORING_CONFIG["multipliers"]["delay"]["ge_24h"])
    if delay_seconds >= 3600:
        return float(SCORING_CONFIG["multipliers"]["delay"]["ge_1h"])
    return float(SCORING_CONFIG["multipliers"]["delay"]["default"])


def get_holder_multiplier(
    holder_type: str | None,
    threshold: int | None = None,
    signers: int | None = None,
    delay_hours: float | None = None,
) -> tuple[float, bool]:
    """
    Returns (holder_mult, delay_handled_in_holder).
    holder_assumed is True when holder_type is None.
    """
    if not holder_type or holder_type == "none" or holder_type == "eoa":
        return 1.0, False

    if holder_type == "contract_unknown":
        return float(SCORING_CONFIG["multipliers"]["holder"]["contract_unknown"]), False

    if holder_type == "renounced":
        return float(SCORING_CONFIG["multipliers"]["holder"]["renounced"]), False

    if holder_type == "timelock_multisig":
        delay_h = delay_hours if delay_hours is not None else 0.0
        if delay_h >= 24:
            # 0.4 replaces delay multiplier so as not to double count
            return float(SCORING_CONFIG["multipliers"]["holder"]["timelock_multisig_ge_24h"]), True
        # If timelock delay < 24h, treat base holder as multisig
        t = threshold or 1
        s = signers or 1
        if t >= 3 and s >= 5:
            return float(SCORING_CONFIG["multipliers"]["holder"]["multisig_threshold_3_signers_5"]), False
        if t >= 2 and s >= 3:
            return float(SCORING_CONFIG["multipliers"]["holder"]["multisig_threshold_2_signers_3"]), False
        return 1.0, False

    if holder_type == "multisig":
        t = threshold or 1
        s = signers or 1
        if t >= 3 and s >= 5:
            return float(SCORING_CONFIG["multipliers"]["holder"]["multisig_threshold_3_signers_5"]), False
        if t >= 2 and s >= 3:
            return float(SCORING_CONFIG["multipliers"]["holder"]["multisig_threshold_2_signers_3"]), False
        return 1.0, False

    return 1.0, False


def compute_action_score(
    power_category: str,
    mitigations: dict[str, Any] | None,
    declaration: dict[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    """
    Calculate single action score:
    action_score = base * (0.6 if cap else 1.0) * delay_mult(max(in_contract_delay, declared_delay))
                   * (0.85 if reversible else 1.0) * holder_mult
    """
    base_scores = SCORING_CONFIG["base_scores"]
    base = base_scores.get(power_category, base_scores["OTHER_PRIVILEGED"])

    mit = mitigations or {}
    has_cap = bool(mit.get("cap"))
    cap_mult = float(SCORING_CONFIG["multipliers"]["cap"]) if has_cap else 1.0

    in_contract_delay = float(mit.get("delay_seconds") or 0)
    decl_delay_hours = float(declaration.get("delay_hours") or 0) if declaration else 0.0
    decl_delay_seconds = decl_delay_hours * 3600.0

    reversible = bool(mit.get("reversible"))
    rev_mult = float(SCORING_CONFIG["multipliers"]["reversible"]) if reversible else 1.0

    holder_type = declaration.get("holder_type") if declaration else None
    threshold = declaration.get("threshold") if declaration else None
    signers = declaration.get("signers") if declaration else None

    holder_mult, delay_handled = get_holder_multiplier(
        holder_type, threshold=threshold, signers=signers, delay_hours=decl_delay_hours
    )

    if delay_handled:
        # declared timelock >= 24h already absorbed in holder_mult (0.4)
        # only apply in-contract delay if in-contract delay itself is >= 24h and stronger
        delay_mult = 1.0
    else:
        effective_delay = max(in_contract_delay, decl_delay_seconds)
        delay_mult = get_delay_multiplier(effective_delay)

    raw_score = base * cap_mult * delay_mult * rev_mult * holder_mult
    final_score = int(round(raw_score))
    final_score = max(0, min(100, final_score))

    breakdown = {
        "base": base,
        "cap_mult": round(cap_mult, 2),
        "delay_mult": round(delay_mult, 2),
        "reversible_mult": round(rev_mult, 2),
        "holder_mult": round(holder_mult, 2),
        "score": final_score,
    }
    return final_score, breakdown


def get_tier(score: int) -> str:
    tiers = SCORING_CONFIG["tiers"]
    if score >= tiers["critical"]:
        return "critical"
    if score >= tiers["high"]:
        return "high"
    if score >= tiers["medium"]:
        return "medium"
    if score >= tiers["low"]:
        return "low"
    return "none"


def compute_role_scores_with_escalation(
    role_keys: list[str],
    role_action_scores: dict[str, list[int]],
    admin_graph: dict[str, list[str]],  # admin_role_key -> list of roles it administers / can grant
    declarations: dict[str, dict[str, Any]],
) -> dict[str, int]:
    """
    role_score = max(its action scores, 0.95 * score of each role it can grant or administer).
    If role is renounced, score is 0.
    """
    escalation_mult = float(SCORING_CONFIG.get("role_escalation_multiplier", 0.95))
    scores: dict[str, int] = {}

    for r in role_keys:
        decl = declarations.get(r, {})
        if decl.get("holder_type") == "renounced":
            scores[r] = 0
        else:
            action_scores = role_action_scores.get(r, [])
            scores[r] = max(action_scores) if action_scores else 0

    # Iterative fixed-point propagation for escalation
    changed = True
    iterations = 0
    max_iter = len(role_keys) + 5
    while changed and iterations < max_iter:
        changed = False
        iterations += 1
        for admin_role, sub_roles in admin_graph.items():
            if admin_role not in scores:
                continue
            admin_decl = declarations.get(admin_role, {})
            if admin_decl.get("holder_type") == "renounced":
                continue
            for sub in sub_roles:
                sub_score = scores.get(sub, 0)
                escalated = int(round(escalation_mult * sub_score))
                if escalated > scores[admin_role]:
                    scores[admin_role] = min(100, escalated)
                    changed = True

    return scores


async def recompute_scores(
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """
    Synchronously recomputes action scores and role scores for an audit
    from stored privileged_actions, role_nodes, and role_declarations.
    Updates privileged_actions and privilege_results in place.
    Target: < 300ms.
    """
    from app.db import PrivilegeResult, PrivilegedAction as PrivilegedActionDB, RoleDeclaration, RoleNode
    from auditor_core.privilege_map.templates import render_worst_case_sentence

    # Load declarations
    decl_rows = (await session.execute(
        select(RoleDeclaration).where(RoleDeclaration.audit_id == audit_id)
    )).scalars().all()
    declarations: dict[str, dict[str, Any]] = {
        d.role_key: {"holder_type": d.holder_type, **d.params} for d in decl_rows
    }

    # Load role nodes
    node_rows = (await session.execute(
        select(RoleNode).where(RoleNode.audit_id == audit_id)
    )).scalars().all()
    role_nodes = {n.role_key: n for n in node_rows}

    # Admin graph: admin_role_key -> [sub_role_keys]
    admin_graph: dict[str, list[str]] = {}
    for r_key, node in role_nodes.items():
        if node.admin_role_key:
            admin_graph.setdefault(node.admin_role_key, []).append(r_key)

    # Load privileged actions
    action_rows = (await session.execute(
        select(PrivilegedActionDB).where(PrivilegedActionDB.audit_id == audit_id)
    )).scalars().all()

    # Calculate action scores
    role_action_scores: dict[str, list[int]] = {r: [] for r in role_nodes}
    role_breakdowns: dict[str, list[dict[str, Any]]] = {r: [] for r in role_nodes}
    role_actions_map: dict[str, list[PrivilegedActionDB]] = {r: [] for r in role_nodes}

    for action in action_rows:
        # If guarded by multiple roles, score per role using role's declaration
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

        # Update action.score with max score across its guard roles (or primary)
        primary_decl = declarations.get(action.guard_roles[0]) if action.guard_roles else None
        act_score, _ = compute_action_score(
            power_category=action.power_category,
            mitigations=action.mitigations,
            declaration=primary_decl,
        )
        # Store updated score in action if different
        action.facts["computed_score"] = act_score

    # Compute role scores with escalation
    role_scores = compute_role_scores_with_escalation(
        role_keys=list(role_nodes.keys()),
        role_action_scores=role_action_scores,
        admin_graph=admin_graph,
        declarations=declarations,
    )

    # Update or insert PrivilegeResult per role
    existing_results = {
        r.role_key: r for r in (await session.execute(
            select(PrivilegeResult).where(PrivilegeResult.audit_id == audit_id)
        )).scalars().all()
    }

    for r_key, node in role_nodes.items():
        final_role_score = role_scores.get(r_key, 0)
        tier = get_tier(final_role_score)
        decl = declarations.get(r_key)
        holder_assumed = decl is None or decl.get("holder_type") in (None, "none")

        worst_case = render_worst_case_sentence(
            role_name=node.display_name,
            actions=role_actions_map.get(r_key, []),
            declaration=decl,
        )

        breakdown_list = role_breakdowns.get(r_key, [])

        if r_key in existing_results:
            res = existing_results[r_key]
            res.blast_score = final_role_score
            res.tier = tier
            res.worst_case = worst_case
            res.holder_assumed = holder_assumed
            res.breakdown = breakdown_list
        else:
            res = PrivilegeResult(
                audit_id=audit_id,
                org_id=org_id,
                role_key=r_key,
                blast_score=final_role_score,
                tier=tier,
                worst_case=worst_case,
                holder_assumed=holder_assumed,
                breakdown=breakdown_list,
            )
            session.add(res)

