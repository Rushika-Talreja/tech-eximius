"""
Role resolution and privileged action mapping.
Handles:
  - Ownable / Ownable2Step -> OWNER
  - AccessControl: bytes32 constants, DEFAULT_ADMIN_ROLE default admin, _setRoleAdmin
  - Custom modifiers: msg.sender == X, isX[msg.sender], hasRole(...) -> CUSTOM:<modifier>
  - Proxies: UUPS _authorizeUpgrade guard, Transparent proxy -> PROXY_ADMIN
  - Inherited & overridden modifiers, internal helper checks
  - Unguarded functions emitting 'missing access control' candidates
"""
from __future__ import annotations

import re
from typing import Any
import uuid

from auditor_schemas.models import PowerCategory
from auditor_core.privilege_map.matchers import classify_power
from auditor_core.privilege_map.mitigations import (
    detect_cap,
    detect_in_contract_delay,
    detect_reversibility,
    detect_two_step_transfer,
)
from auditor_core.privilege_map.semantic import ContractSemanticModel, FunctionSemantic, ModifierSemantic


def format_role_display_name(role_key: str) -> str:
    """Format user-facing display name for a role key."""
    if role_key == "OWNER":
        return "Owner"
    if role_key == "DEFAULT_ADMIN_ROLE":
        return "Default Admin"
    if role_key == "PROXY_ADMIN":
        return "Proxy Admin"
    if role_key.startswith("CUSTOM:"):
        raw = role_key[len("CUSTOM:"):]
        # Convert camelCase to Title Case: onlyAdmin -> Only Admin
        words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", raw)
        return "Custom: " + (" ".join(w.capitalize() for w in words) if words else raw)
    if role_key.endswith("_ROLE"):
        raw = role_key[:-len("_ROLE")]
        return raw.replace("_", " ").title()
    return role_key.replace("_", " ").title()


def resolve_roles_and_actions(
    contracts: dict[str, ContractSemanticModel],
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    contract_db_ids: dict[str, uuid.UUID],
    file_db_ids: dict[str, uuid.UUID],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """
    Resolves role nodes, privileged actions, missing access control candidates, and notes.
    Returns:
      (role_nodes_dict, privileged_actions_list, missing_access_control_candidates, undetected_notes)
    """
    role_nodes: dict[str, dict[str, Any]] = {}
    privileged_actions: list[dict[str, Any]] = []
    missing_access_control_candidates: list[dict[str, Any]] = []
    undetected_notes: list[str] = []

    # 1. Collect all undetected notes from semantic models
    for c in contracts.values():
        for note in c.undetected_notes:
            if note not in undetected_notes:
                undetected_notes.append(note)

    # 2. Build global modifier registry with inheritance support
    # contract_name -> {mod_name -> ModifierSemantic}
    contract_modifiers: dict[str, dict[str, ModifierSemantic]] = {}
    for c_name, c in contracts.items():
        contract_modifiers[c_name] = {m.name: m for m in c.modifiers}

    # Resolve inherited modifiers
    for c_name, c in contracts.items():
        for base in c.inheritance:
            if base in contract_modifiers:
                for mod_name, mod_obj in contract_modifiers[base].items():
                    if mod_name not in contract_modifiers[c_name]:
                        contract_modifiers[c_name][mod_name] = mod_obj

    # Inspect internal helper functions called inside modifier bodies
    for c_name, c in contracts.items():
        fn_map = {f.name: f for f in c.functions}
        for m_name, m in contract_modifiers[c_name].items():
            if not m.has_msg_sender_check and not m.role_checked:
                for fn_name, fn_obj in fn_map.items():
                    if fn_name in m.body_source:
                        if "msg.sender" in fn_obj.body_source:
                            m.has_msg_sender_check = True
                            if "msg.sender == owner" in fn_obj.body_source:
                                m.checked_variable = "owner"
                            elif "msg.sender == admin" in fn_obj.body_source:
                                m.checked_variable = "admin"

    # 3. Discover roles
    # Check Ownable
    has_ownable = False
    for c in contracts.values():
        inh_lower = [str(i).lower() for i in c.inheritance]
        if any(o in inh_lower for o in ("ownable", "ownable2step", "ownableupgradeable")):
            has_ownable = True
            break
        if "onlyOwner" in contract_modifiers.get(c.name, {}):
            has_ownable = True
            break
        for f in c.functions:
            if any("onlyOwner" in mod for mod in f.modifiers):
                has_ownable = True
                break

    if has_ownable:
        role_nodes["OWNER"] = {
            "role_key": "OWNER",
            "display_name": "Owner",
            "kind": "owner",
            "admin_role_key": None,
        }

    # Check AccessControl
    has_access_control = False
    role_admins: dict[str, str] = {}  # role -> admin_role
    for c in contracts.values():
        inh_lower = [str(i).lower() for i in c.inheritance]
        if any("accesscontrol" in i for i in inh_lower):
            has_access_control = True

        # Scan for bytes32 role constants
        for var in c.state_variables:
            if var.type_name == "bytes32" and var.is_constant:
                if var.name.endswith("_ROLE") or var.name == "DEFAULT_ADMIN_ROLE":
                    has_access_control = True
                    role_nodes[var.name] = {
                        "role_key": var.name,
                        "display_name": format_role_display_name(var.name),
                        "kind": "access_control",
                        "admin_role_key": "DEFAULT_ADMIN_ROLE",
                    }

        # Scan source / function bodies for _setRoleAdmin(role, adminRole)
        for f in c.functions:
            body = f.body_source
            set_admin_matches = re.findall(r"_setRoleAdmin\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)", body)
            for role_name, admin_name in set_admin_matches:
                role_admins[role_name] = admin_name

    if has_access_control:
        if "DEFAULT_ADMIN_ROLE" not in role_nodes:
            role_nodes["DEFAULT_ADMIN_ROLE"] = {
                "role_key": "DEFAULT_ADMIN_ROLE",
                "display_name": "Default Admin",
                "kind": "access_control",
                "admin_role_key": None,
            }
        # Update admin roles from _setRoleAdmin
        for r_name, adm_name in role_admins.items():
            if r_name in role_nodes:
                role_nodes[r_name]["admin_role_key"] = adm_name
                if adm_name not in role_nodes:
                    role_nodes[adm_name] = {
                        "role_key": adm_name,
                        "display_name": format_role_display_name(adm_name),
                        "kind": "access_control",
                        "admin_role_key": "DEFAULT_ADMIN_ROLE",
                    }

    # Check Custom Modifiers & Proxies
    for c_name, c in contracts.items():
        if c.upgradeability in ("transparent", "proxy_admin"):
            role_nodes["PROXY_ADMIN"] = {
                "role_key": "PROXY_ADMIN",
                "display_name": "Proxy Admin",
                "kind": "proxy_admin",
                "admin_role_key": None,
            }

        for m_name, m in contract_modifiers[c_name].items():
            if m_name in ("onlyOwner", "onlyRole"):
                continue
            if m.has_msg_sender_check or m.role_checked:
                if m.role_checked and m.role_checked in role_nodes:
                    continue
                custom_key = f"CUSTOM:{m_name}"
                role_nodes[custom_key] = {
                    "role_key": custom_key,
                    "display_name": format_role_display_name(custom_key),
                    "kind": "custom",
                    "admin_role_key": "OWNER" if has_ownable else None,
                }

    # 4. Map functions to guard roles and identify privileged actions
    for c_name, c in contracts.items():
        # Only analyze concrete contracts for privileged action execution
        if c.kind in ("interface", "library", "abstract"):
            continue

        c_mods = contract_modifiers.get(c_name, {})
        contract_db_id = contract_db_ids.get(c_name, uuid.uuid4())

        for fn in c.functions:
            # Skip view and pure functions (cannot execute privileged state changes)
            if fn.state_mutability in ("view", "pure"):
                continue
            # Include public/external functions, plus UUPS _authorizeUpgrade (which is internal)
            if fn.visibility not in ("public", "external") and fn.name != "_authorizeUpgrade":
                continue

            guard_roles: list[str] = []
            guard_kind = "none"

            # Check applied modifiers
            for mod_invocation in fn.modifiers:
                mod_name = mod_invocation.split("(")[0].strip()
                if mod_name == "onlyOwner":
                    guard_roles.append("OWNER")
                    guard_kind = "modifier"
                elif mod_name == "onlyRole":
                    role_arg_match = re.search(r"onlyRole\s*\(\s*([a-zA-Z0-9_]+)\s*\)", mod_invocation)
                    if role_arg_match:
                        r_name = role_arg_match.group(1)
                        guard_roles.append(r_name)
                        guard_kind = "role_check"
                        if r_name not in role_nodes:
                            role_nodes[r_name] = {
                                "role_key": r_name,
                                "display_name": format_role_display_name(r_name),
                                "kind": "access_control",
                                "admin_role_key": "DEFAULT_ADMIN_ROLE",
                            }
                elif mod_name in ("onlyAdmin", "onlyGovernor", "onlyGovernance"):
                    custom_key = f"CUSTOM:{mod_name}"
                    guard_roles.append(custom_key)
                    guard_kind = "modifier"
                elif mod_name in c_mods:
                    mod_obj = c_mods[mod_name]
                    if mod_obj.role_checked and mod_obj.role_checked in role_nodes:
                        guard_roles.append(mod_obj.role_checked)
                        guard_kind = "role_check"
                    elif mod_obj.has_msg_sender_check:
                        custom_key = f"CUSTOM:{mod_name}"
                        guard_roles.append(custom_key)
                        guard_kind = "modifier"

            # Check modifier invocations with arguments: onlyRole(ROLE)
            # Find in function header/body
            for m_call in re.findall(r"onlyRole\s*\(\s*([a-zA-Z0-9_]+)\s*\)", fn.body_source + " " + " ".join(fn.modifiers)):
                if m_call in role_nodes:
                    guard_roles.append(m_call)
                    guard_kind = "role_check"

            # Check internal helper calls / direct sender checks in body
            if not guard_roles:
                if "_checkOwner()" in fn.body_source or "require(msg.sender == owner" in fn.body_source or "require(owner == msg.sender" in fn.body_source:
                    guard_roles.append("OWNER")
                    guard_kind = "require_sender"
                elif "require(msg.sender == admin" in fn.body_source or "_checkAdmin()" in fn.body_source:
                    custom_key = "CUSTOM:onlyAdmin"
                    guard_roles.append(custom_key)
                    guard_kind = "require_sender"
                elif "_checkRole(" in fn.body_source:
                    match_role = re.search(r"_checkRole\s*\(\s*([a-zA-Z0-9_]+)", fn.body_source)
                    if match_role and match_role.group(1) in role_nodes:
                        guard_roles.append(match_role.group(1))
                        guard_kind = "role_check"

            # UUPS _authorizeUpgrade check
            if fn.name == "_authorizeUpgrade":
                if not guard_roles and has_ownable:
                    guard_roles.append("OWNER")
                    guard_kind = "modifier"

            # Deduplicate guard roles
            guard_roles = list(dict.fromkeys(guard_roles))

            # Classify power category
            fn_dict = fn.model_dump()
            fn_dict["contract_name"] = c_name
            category, facts = classify_power(fn_dict)

            file_db_id = file_db_ids.get(fn.span.file, uuid.uuid4())

            if guard_roles:
                # Gated privileged function -> Privilege Map
                # Mitigations
                c_dict = c.model_dump()
                cap_info = detect_cap(fn_dict, c_dict)
                delay_sec = detect_in_contract_delay(fn_dict, c_dict)
                two_step = detect_two_step_transfer(fn_dict, c_dict)
                all_guarded = [f.model_dump() for f in c.functions if f.modifiers]
                reversible = detect_reversibility(fn_dict, c_dict, all_guarded)

                # Funds impact heuristic
                if category in (PowerCategory.SELFDESTRUCT_OR_DELEGATECALL, PowerCategory.UPGRADE, PowerCategory.WITHDRAW_FUNDS, PowerCategory.MINT):
                    funds_impact = 3
                elif category in (PowerCategory.CHANGE_ORACLE, PowerCategory.BURN_OTHERS, PowerCategory.BLACKLIST_FREEZE, PowerCategory.GRANT_ROLE):
                    funds_impact = 2
                elif category in (PowerCategory.CHANGE_FEE, PowerCategory.CHANGE_PARAMETER, PowerCategory.PAUSE):
                    funds_impact = 1
                else:
                    funds_impact = 0

                mitigations_data = {
                    "cap": cap_info,
                    "delay_seconds": delay_sec,
                    "two_step": two_step,
                    "reversible": reversible,
                }

                privileged_actions.append({
                    "id": uuid.uuid4(),
                    "audit_id": audit_id,
                    "org_id": org_id,
                    "contract_id": contract_db_id,
                    "file_id": file_db_id,
                    "contract": c_name,
                    "function_signature": fn.signature,
                    "start_line": fn.span.start_line,
                    "end_line": fn.span.end_line,
                    "span": fn.span.model_dump(),
                    "power_category": category.value,
                    "guard_kind": guard_kind,
                    "guard_roles": guard_roles,
                    "mitigations": mitigations_data,
                    "funds_impact": funds_impact,
                    "facts": {**facts, "contract_name": c_name},
                })
            else:
                # UNGUARDED function
                # If it makes privileged-category writes, do NOT put in map; emit candidate
                if category != PowerCategory.OTHER_PRIVILEGED or len(fn.state_writes) > 0:
                    missing_access_control_candidates.append({
                        "contract": c_name,
                        "function_signature": fn.signature,
                        "power_category": category.value,
                        "span": fn.span.model_dump(),
                        "state_writes": fn.state_writes,
                        "reason": "Missing access control on privileged state-changing function",
                    })

    return role_nodes, privileged_actions, missing_access_control_candidates, undetected_notes
