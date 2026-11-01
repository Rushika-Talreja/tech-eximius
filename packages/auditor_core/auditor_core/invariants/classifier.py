"""
Contract type classifier for Invariant Hunter Lite (Milestone 7).
Classifies contracts into: erc20, erc4626, staking, lending, other.
Returns (contract_type, confidence).
Supports user override.
"""
from __future__ import annotations


def classify_contract_type_with_confidence(
    function_names: set[str],
    inheritance: list[str],
    override: str | None = None,
) -> tuple[str, float]:
    """
    Classify contract into: erc20, erc4626, staking, lending, other.
    Returns (contract_type, confidence: float between 0.0 and 1.0).
    """
    if override:
        valid_overrides = {"erc20", "erc4626", "staking", "lending", "other"}
        clean_override = override.strip().lower()
        if clean_override in valid_overrides:
            return clean_override, 1.0

    inh_lower = [str(i).lower() for i in inheritance]

    # ERC4626 checks
    erc4626_core = {"asset", "totalAssets", "convertToShares", "convertToAssets", "previewDeposit", "previewRedeem"}
    has_erc4626_inh = any("erc4626" in i for i in inh_lower)
    erc4626_matches = erc4626_core.intersection(function_names)
    if has_erc4626_inh or len(erc4626_matches) >= 3:
        confidence = 0.95 if has_erc4626_inh else min(0.9, 0.5 + (len(erc4626_matches) / len(erc4626_core)) * 0.4)
        return "erc4626", round(confidence, 2)

    # ERC20 checks
    erc20_core = {"totalSupply", "balanceOf", "transfer", "transferFrom", "approve"}
    has_erc20_inh = any("erc20" in i for i in inh_lower)
    erc20_matches = erc20_core.intersection(function_names)
    if has_erc20_inh or len(erc20_matches) >= 3:
        confidence = 0.95 if has_erc20_inh else min(0.9, 0.5 + (len(erc20_matches) / len(erc20_core)) * 0.4)
        return "erc20", round(confidence, 2)

    # Staking checks
    staking_core = {"stake", "unstake", "claimReward", "getReward", "rewardRate"}
    has_staking_inh = any("staking" in i for i in inh_lower)
    staking_matches = staking_core.intersection(function_names)
    if has_staking_inh or len(staking_matches) >= 2:
        confidence = 0.95 if has_staking_inh else min(0.85, 0.5 + (len(staking_matches) / len(staking_core)) * 0.35)
        return "staking", round(confidence, 2)

    # Lending checks
    lending_core = {"borrow", "repay", "liquidate", "borrowRate", "collateralFactor", "totalBorrows"}
    has_lending_inh = any("lending" in i for i in inh_lower)
    lending_matches = lending_core.intersection(function_names)
    if has_lending_inh or len(lending_matches) >= 2:
        confidence = 0.95 if has_lending_inh else min(0.85, 0.5 + (len(lending_matches) / len(lending_core)) * 0.35)
        return "lending", round(confidence, 2)

    return "other", 0.5
