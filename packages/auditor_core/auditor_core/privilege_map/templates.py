"""
Template-based worst-case explanation text for Privilege Map.
Purely deterministic, filled with extracted facts, no LLM.
Always appends a mitigation sentence.
"""
from __future__ import annotations

from typing import Any


CATEGORY_TEMPLATES = {
    "MINT": "{role} can mint {cap_text} tokens to any address {delay_clause}.",
    "WITHDRAW_FUNDS": "{role} can withdraw funds from {contract} {delay_clause}.",
    "UPGRADE": "{role} can upgrade contract {contract} to arbitrary logic {delay_clause}.",
    "SELFDESTRUCT_OR_DELEGATECALL": "{role} can trigger selfdestruct or delegatecall to arbitrary contracts in {contract} {delay_clause}.",
    "CHANGE_ORACLE": "{role} can change the oracle or price feed in {contract} {delay_clause}.",
    "BURN_OTHERS": "{role} can burn tokens held by other accounts in {contract} {delay_clause}.",
    "BLACKLIST_FREEZE": "{role} can blacklist accounts or freeze transfers in {contract} {delay_clause}.",
    "GRANT_ROLE": "{role} can grant or revoke privileged roles in {contract} {delay_clause}.",
    "CHANGE_FEE": "{role} can modify fee parameters in {contract} {delay_clause}.",
    "CHANGE_PARAMETER": "{role} can modify critical protocol parameters in {contract} {delay_clause}.",
    "PAUSE": "{role} can pause contract operations in {contract} {delay_clause}.",
    "OTHER_PRIVILEGED": "{role} can execute privileged operations in {contract} {delay_clause}.",
}

CATEGORY_RANK = {
    "SELFDESTRUCT_OR_DELEGATECALL": 12,
    "UPGRADE": 11,
    "WITHDRAW_FUNDS": 10,
    "MINT": 9,
    "CHANGE_ORACLE": 8,
    "BURN_OTHERS": 7,
    "BLACKLIST_FREEZE": 6,
    "GRANT_ROLE": 5,
    "CHANGE_FEE": 4,
    "CHANGE_PARAMETER": 3,
    "PAUSE": 2,
    "OTHER_PRIVILEGED": 1,
}


def render_mitigation_sentence(
    declaration: dict[str, Any] | None,
    detected_cap: bool = False,
    detected_delay_seconds: int = 0,
) -> str:
    """Render the standard mitigation sentence."""
    if not declaration or declaration.get("holder_type") in (None, "none", "eoa"):
        parts = []
        if detected_delay_seconds >= 3600:
            parts.append(f"{detected_delay_seconds // 3600}h in-contract delay")
        if detected_cap:
            parts.append("supply cap")
        if parts:
            return f"In-contract mitigations: {', '.join(parts)}. No multisig assumed."
        return "No timelock, no cap, no multisig assumed."

    ht = declaration.get("holder_type")
    if ht == "renounced":
        return "Declared: renounced."
    if ht == "contract_unknown":
        return "Declared: contract unknown."

    declared_parts: list[str] = []
    t = declaration.get("threshold")
    s = declaration.get("signers")
    if t and s:
        declared_parts.append(f"{t}-of-{s} multisig")
    elif ht == "multisig":
        declared_parts.append("multisig")

    dh = declaration.get("delay_hours")
    if dh is not None and dh > 0:
        dh_int = int(dh) if dh == int(dh) else dh
        declared_parts.append(f"{dh_int}h timelock")
    elif ht == "timelock_multisig":
        declared_parts.append("timelock")

    if detected_cap:
        declared_parts.append("supply cap")

    if declared_parts:
        return f"Declared: {', '.join(declared_parts)}."
    return "No timelock, no cap, no multisig assumed."


def render_worst_case_sentence(
    role_name: str,
    actions: list[Any],
    declaration: dict[str, Any] | None = None,
) -> str:
    """
    Renders worst-case description for a role based on its highest-risk action.
    """
    if not actions:
        mit_sentence = render_mitigation_sentence(declaration)
        return f"{role_name} has no direct privileged actions. {mit_sentence}"

    # Pick the highest impact action
    sorted_actions = sorted(
        actions,
        key=lambda a: (
            CATEGORY_RANK.get(getattr(a, "power_category", ""), 0),
            getattr(a, "funds_impact", 0),
        ),
        reverse=True,
    )
    worst_action = sorted_actions[0]

    category = getattr(worst_action, "power_category", "OTHER_PRIVILEGED")
    mitigations = getattr(worst_action, "mitigations", {}) or {}
    facts = getattr(worst_action, "facts", {}) or {}

    contract = facts.get("contract_name") or getattr(worst_action, "contract", "Contract") or "the contract"
    cap_info = mitigations.get("cap")
    delay_sec = mitigations.get("delay_seconds") or 0

    if cap_info and cap_info.get("value"):
        cap_text = f"up to {cap_info['value']}"
    elif cap_info:
        cap_text = "capped"
    else:
        cap_text = "unbounded"

    if delay_sec >= 3600:
        delay_clause = f"after a {delay_sec // 3600}h delay"
    elif delay_sec > 0:
        delay_clause = f"after a {delay_sec}s delay"
    else:
        delay_clause = "with no delay"

    template = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["OTHER_PRIVILEGED"])
    action_sentence = template.format(
        role=role_name,
        contract=contract,
        cap_text=cap_text,
        delay_clause=delay_clause,
    )

    mit_sentence = render_mitigation_sentence(
        declaration,
        detected_cap=bool(cap_info),
        detected_delay_seconds=delay_sec,
    )

    return f"{action_sentence} {mit_sentence}"

