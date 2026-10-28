"""
Pure, separately unit-tested power category matchers for Privilege Map.
One function per category returning (matched: bool, facts: dict).
Categories and base scores:
  SELFDESTRUCT_OR_DELEGATECALL: 100
  UPGRADE: 95
  WITHDRAW_FUNDS: 90
  MINT: 85
  CHANGE_ORACLE: 80
  BURN_OTHERS: 75
  BLACKLIST_FREEZE: 70
  GRANT_ROLE: 60
  CHANGE_FEE: 55
  CHANGE_PARAMETER: 45
  PAUSE: 40
  OTHER_PRIVILEGED: 30
"""
from __future__ import annotations

import re
from typing import Any
from auditor_schemas.models import PowerCategory

BASE_SCORES: dict[str, int] = {
    PowerCategory.SELFDESTRUCT_OR_DELEGATECALL: 100,
    PowerCategory.UPGRADE: 95,
    PowerCategory.WITHDRAW_FUNDS: 90,
    PowerCategory.MINT: 85,
    PowerCategory.CHANGE_ORACLE: 80,
    PowerCategory.BURN_OTHERS: 75,
    PowerCategory.BLACKLIST_FREEZE: 70,
    PowerCategory.GRANT_ROLE: 60,
    PowerCategory.CHANGE_FEE: 55,
    PowerCategory.CHANGE_PARAMETER: 45,
    PowerCategory.PAUSE: 40,
    PowerCategory.OTHER_PRIVILEGED: 30,
}


def match_selfdestruct_or_delegatecall(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: SELFDESTRUCT_OR_DELEGATECALL (100)."""
    if fn.get("has_selfdestruct"):
        return True, {"mechanism": "selfdestruct"}
    if fn.get("has_delegatecall"):
        return True, {"mechanism": "delegatecall"}

    body = fn.get("body_source", "") or ""
    if re.search(r"\bselfdestruct\s*\(", body) or re.search(r"\bsuicide\s*\(", body):
        return True, {"mechanism": "selfdestruct_in_body"}
    if re.search(r"\.delegatecall\s*\(", body):
        return True, {"mechanism": "delegatecall_in_body"}

    return False, {}


def match_upgrade(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: UPGRADE (95)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    upgrade_names = {
        "_authorizeUpgrade",
        "upgradeTo",
        "upgradeToAndCall",
        "changeAdmin",
        "setImplementation",
        "upgradeBeacon",
        "setBeacon",
    }
    if name in upgrade_names or re.match(r"^upgradeTo.*", name):
        return True, {"upgrade_function": name}

    # Writes to EIP-1967 implementation slot
    eip1967_impl_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    if eip1967_impl_slot in body.lower():
        return True, {"upgrade_slot": eip1967_impl_slot}

    return False, {}


def match_withdraw_funds(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: WITHDRAW_FUNDS (90)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    withdraw_names = {
        "emergencyDrain",
        "emergencyWithdraw",
        "withdrawAll",
        "drain",
        "sweep",
        "rescueFunds",
        "withdrawFunds",
        "sweepTokens",
        "adminWithdraw",
        "emergencyTransfer",
    }
    if name in withdraw_names:
        return True, {"mechanism": "named_drain_function", "name": name}

    # Token flows: check if any eth send or token transfer sent to caller/param without balance reduction
    token_flows = fn.get("token_flows", [])
    for flow in token_flows:
        if flow.get("kind") in ("eth_send", "transfer", "transfer_from"):
            # If function is administrative/guarded and transfers funds
            return True, {"mechanism": "token_or_eth_transfer", "flow": flow}

    if re.search(r"\.call\s*\{\s*value\s*:", body) or re.search(r"\.transfer\s*\(", body) or re.search(r"safeTransfer\s*\(", body):
        # Look for address(this).balance or arbitrary receiver
        if "address(this).balance" in body or re.search(r"\b(owner|msg\.sender|receiver|to)\.call", body):
            return True, {"mechanism": "direct_funds_transfer"}

    return False, {}


def match_mint(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: MINT (85)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    mint_names = {"mint", "mintTo", "issueTokens", "safeMint", "mintBatch", "_mint"}
    if name in mint_names:
        return True, {"mint_function": name}

    token_flows = fn.get("token_flows", [])
    for flow in token_flows:
        if flow.get("kind") == "mint":
            return True, {"mechanism": "_mint_call", "flow": flow}

    if re.search(r"\b_mint\s*\(", body) or re.search(r"\b_safeMint\s*\(", body):
        return True, {"mechanism": "internal_mint_call"}

    # Direct totalSupply increment and balance increment
    if "totalSupply +=" in body or "totalSupply =" in body:
        if "balances[" in body:
            return True, {"mechanism": "direct_supply_increment"}

    return False, {}


def match_change_oracle(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: CHANGE_ORACLE (80)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    oracle_names = {
        "setOracle",
        "setPriceFeed",
        "updateOracle",
        "setPriceSource",
        "setAggregator",
        "changeOracle",
        "setFeed",
    }
    if name in oracle_names:
        return True, {"oracle_function": name}

    # Writes to state variable named oracle / priceFeed
    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        var_lower = var.lower()
        if any(keyword in var_lower for keyword in ("oracle", "pricefeed", "aggregator", "pricesource")):
            return True, {"oracle_variable": var}

    # Body check for assignment to oracle variable
    if re.search(r"\b(oracle|priceFeed|aggregator|priceSource)\s*=", body, re.IGNORECASE):
        return True, {"mechanism": "oracle_assignment_in_body"}

    return False, {}


def match_burn_others(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: BURN_OTHERS (75)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    burn_others_names = {"burnFrom", "burnOther", "adminBurn", "slash", "burnAccount"}
    if name in burn_others_names:
        return True, {"burn_function": name}

    token_flows = fn.get("token_flows", [])
    for flow in token_flows:
        if flow.get("kind") == "burn" and flow.get("target") != "msg.sender":
            return True, {"mechanism": "burn_non_caller", "flow": flow}

    if re.search(r"\b_burn\s*\(\s*(?!msg\.sender\b)(\w+)", body):
        return True, {"mechanism": "burn_call_not_caller"}

    return False, {}


def match_blacklist_freeze(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: BLACKLIST_FREEZE (70)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    freeze_names = {
        "blacklist",
        "unblacklist",
        "freeze",
        "unfreeze",
        "freezeAccount",
        "setBlacklist",
        "blockAddress",
        "setBlocked",
        "setFrozen",
    }
    if name in freeze_names:
        return True, {"freeze_function": name}

    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        var_lower = var.lower()
        if any(keyword in var_lower for keyword in ("blacklist", "frozen", "freeze", "blocked")):
            return True, {"freeze_variable": var}

    if re.search(r"\b(isBlacklisted|blacklisted|frozen|isFrozen|blocked)\s*\[", body, re.IGNORECASE):
        return True, {"mechanism": "blacklist_mapping_write"}

    return False, {}


def match_grant_role(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: GRANT_ROLE (60)."""
    name = fn.get("name", "")
    role_names = {
        "grantRole",
        "revokeRole",
        "transferOwnership",
        "setRoleAdmin",
        "setAdmin",
        "changeAdmin",
        "transferAdmin",
        "renounceOwnership",
        "addAdmin",
        "removeAdmin",
        "setOwner",
        "nominateNewOwner",
    }
    if name in role_names:
        return True, {"role_management_function": name}

    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        if var.lower() in ("owner", "_owner", "admin", "pendingowner"):
            return True, {"owner_var_write": var}

    body = fn.get("body_source", "") or ""
    if re.search(r"\bgrantRole\s*\(", body) or re.search(r"\brevokeRole\s*\(", body):
        return True, {"mechanism": "grant_role_call"}

    return False, {}


def match_change_fee(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: CHANGE_FEE (55)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    fee_names = {
        "setFee",
        "setProtocolFee",
        "setPerformanceFee",
        "setTaxFee",
        "updateFee",
        "setFeeBps",
        "setManagementFee",
        "setWithdrawFee",
        "setDepositFee",
    }
    if name in fee_names:
        return True, {"fee_function": name}

    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        var_lower = var.lower()
        if any(k in var_lower for k in ("fee", "feebps", "taxrate", "protocolfee", "performancefee")):
            return True, {"fee_variable": var}

    if re.search(r"\b(fee|feeBps|taxRate|protocolFee|performanceFee)\s*=", body, re.IGNORECASE):
        return True, {"mechanism": "fee_variable_assignment"}

    return False, {}


def match_change_parameter(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: CHANGE_PARAMETER (45)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    param_names = {
        "setLTV",
        "setCollateralFactor",
        "setInterestRate",
        "setParameter",
        "setConfig",
        "setMaxDeposit",
        "setBorrowRate",
        "setLiquidationThreshold",
        "setRatio",
        "setMultiplier",
        "setCooldown",
    }
    if name in param_names:
        return True, {"parameter_function": name}

    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        var_lower = var.lower()
        if any(k in var_lower for k in ("ltv", "collateralfactor", "interestrate", "liquidationthreshold", "ratio", "multiplier", "cooldown")):
            return True, {"parameter_variable": var}

    return False, {}


def match_pause(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: PAUSE (40)."""
    name = fn.get("name", "")
    body = fn.get("body_source", "") or ""

    pause_names = {
        "pause",
        "unpause",
        "setPaused",
        "pauseVault",
        "setEmergencyStop",
        "emergencyStop",
        "_pause",
        "_unpause",
    }
    if name in pause_names:
        return True, {"pause_function": name}

    written_vars = fn.get("state_writes", [])
    for var in written_vars:
        if var.lower() in ("paused", "_paused", "ispaused", "emergencystop"):
            return True, {"pause_variable": var}

    if re.search(r"\b(paused|_paused|isPaused)\s*=", body):
        return True, {"mechanism": "pause_variable_assignment"}

    return False, {}


def match_other_privileged(fn: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Category: OTHER_PRIVILEGED (30). Fallback when unclear, never guess."""
    return True, {"reason": "other_guarded_state_write"}


MATCHERS_IN_ORDER = [
    (PowerCategory.SELFDESTRUCT_OR_DELEGATECALL, match_selfdestruct_or_delegatecall),
    (PowerCategory.UPGRADE, match_upgrade),
    (PowerCategory.WITHDRAW_FUNDS, match_withdraw_funds),
    (PowerCategory.MINT, match_mint),
    (PowerCategory.CHANGE_ORACLE, match_change_oracle),
    (PowerCategory.BURN_OTHERS, match_burn_others),
    (PowerCategory.BLACKLIST_FREEZE, match_blacklist_freeze),
    (PowerCategory.GRANT_ROLE, match_grant_role),
    (PowerCategory.CHANGE_FEE, match_change_fee),
    (PowerCategory.CHANGE_PARAMETER, match_change_parameter),
    (PowerCategory.PAUSE, match_pause),
    (PowerCategory.OTHER_PRIVILEGED, match_other_privileged),
]


def classify_power(fn: dict[str, Any]) -> tuple[PowerCategory, dict[str, Any]]:
    """
    Evaluates power category matchers in priority order.
    Returns (category, extracted_facts).
    """
    for category, matcher in MATCHERS_IN_ORDER:
        matched, facts = matcher(fn)
        if matched:
            return category, facts
    return PowerCategory.OTHER_PRIVILEGED, {"reason": "fallback"}

