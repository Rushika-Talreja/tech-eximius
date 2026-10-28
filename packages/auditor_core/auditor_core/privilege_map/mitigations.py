"""
Mitigation detection for Privilege Map.
Detects:
  - Cap/bound: require(x <= CONSTANT), maxSupply, ERC20Capped, cap()
  - In-contract delay: queue/execute with timestamps, TimelockController, pending+effectiveAt
  - Two-step transfer: Ownable2Step, acceptOwnership
  - Reversibility: counterpart function exists and is guarded equally
"""
from __future__ import annotations

import re
from typing import Any


def detect_cap(fn: dict[str, Any], contract_semantic: dict[str, Any]) -> dict[str, Any] | None:
    """
    Detect cap / upper bound on state changes or mints.
    Returns {"value": str_or_int, "symbol": ...} if detected, else None.
    """
    body = fn.get("body_source", "") or ""
    inheritance = [str(b).lower() for b in contract_semantic.get("inheritance", [])]

    # Check ERC20Capped inheritance
    if any("erc20capped" in b for b in inheritance):
        # Look for cap() or constructor cap
        return {"value": "cap()", "kind": "ERC20Capped"}

    # Check for require(x <= CONSTANT) or require(totalSupply + amount <= maxSupply)
    cap_patterns = [
        r"require\s*\([^;]*<=\s*([A-Z0-9_]+)",
        r"require\s*\([^;]*maxSupply",
        r"require\s*\([^;]*CAP\b",
        r"require\s*\([^;]*MAX_[A-Z0-9_]+",
        r"if\s*\([^;]*>\s*([A-Z0-9_]+)\s*\)\s*revert",
    ]
    for pattern in cap_patterns:
        match = re.search(pattern, body)
        if match:
            val = match.group(1) if match.groups() else "bounded"
            return {"value": val, "kind": "require_bound"}

    return None


def detect_in_contract_delay(fn: dict[str, Any], contract_semantic: dict[str, Any]) -> int:
    """
    Detect in-contract delay in seconds.
    Returns delay_seconds (int).
    """
    body = fn.get("body_source", "") or ""
    inheritance = [str(b).lower() for b in contract_semantic.get("inheritance", [])]

    # Check TimelockController
    if any("timelockcontroller" in b for b in inheritance):
        return 86400  # Default 24h for TimelockController if not specified

    # Check for queue/execute patterns with timestamp check
    # e.g., require(block.timestamp >= queuedAt + DELAY)
    if "block.timestamp" in body or "block.number" in body:
        delay_match = re.search(r"block\.timestamp\s*>=\s*\w+\s*\+\s*([0-9]+)\s*(days|hours|minutes|seconds)?", body)
        if delay_match:
            val = int(delay_match.group(1))
            unit = delay_match.group(2)
            if unit == "days":
                return val * 86400
            elif unit == "hours":
                return val * 3600
            elif unit == "minutes":
                return val * 60
            return val

        # Common constant delay names in contract
        if "delay" in body.lower() or "timelock" in body.lower() or "effectiveat" in body.lower():
            if "24 hours" in body or "1 days" in body:
                return 86400
            if "48 hours" in body or "2 days" in body:
                return 172800
            if "1 hours" in body or "3600" in body:
                return 3600
            return 3600  # Conservative 1h minimum detected delay

    return 0


def detect_two_step_transfer(fn: dict[str, Any], contract_semantic: dict[str, Any]) -> bool:
    """
    Detect two-step ownership or role transfer (e.g. Ownable2Step, acceptOwnership).
    """
    inheritance = [str(b).lower() for b in contract_semantic.get("inheritance", [])]
    if any("ownable2step" in b for b in inheritance):
        return True

    all_fn_names = {f.get("name") for f in contract_semantic.get("functions", [])}
    if "acceptOwnership" in all_fn_names or "claimOwnership" in all_fn_names:
        return True

    body = fn.get("body_source", "") or ""
    if "pendingOwner" in body or "pendingAdmin" in body:
        return True

    return False


def detect_reversibility(
    fn: dict[str, Any],
    contract_semantic: dict[str, Any],
    all_guarded_functions: list[dict[str, Any]],
) -> bool:
    """
    Detect if a counterpart function exists and is guarded equally.
    e.g. pause <-> unpause, blacklist <-> unblacklist, freeze <-> unfreeze.
    """
    name = fn.get("name", "")
    fn_guards = set(fn.get("guard_roles", []))

    counterpart_pairs = [
        ("pause", "unpause"),
        ("pauseVault", "unpauseVault"),
        ("freeze", "unfreeze"),
        ("blacklist", "unblacklist"),
        ("freezeAccount", "unfreezeAccount"),
        ("blockAddress", "unblockAddress"),
        ("setPaused", "setPaused"),  # if takes a boolean parameter
        ("grantRole", "revokeRole"),
        ("addAdmin", "removeAdmin"),
    ]

    for a, b in counterpart_pairs:
        target_name = None
        if name == a:
            target_name = b
        elif name == b:
            target_name = a

        if target_name:
            if target_name == name:
                # Same function like setPaused(bool) with both true and false paths
                params = fn.get("parameters", [])
                if any(p.get("type") == "bool" for p in params):
                    return True
            else:
                for other in all_guarded_functions:
                    if other.get("name") == target_name:
                        other_guards = set(other.get("guard_roles", []))
                        if fn_guards == other_guards or not fn_guards:
                            return True

    return False

