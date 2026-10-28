"""
Unit tests for all 12 power category matchers (positive and negative cases).
Categories:
  1. SELFDESTRUCT_OR_DELEGATECALL (100)
  2. UPGRADE (95)
  3. WITHDRAW_FUNDS (90)
  4. MINT (85)
  5. CHANGE_ORACLE (80)
  6. BURN_OTHERS (75)
  7. BLACKLIST_FREEZE (70)
  8. GRANT_ROLE (60)
  9. CHANGE_FEE (55)
  10. CHANGE_PARAMETER (45)
  11. PAUSE (40)
  12. OTHER_PRIVILEGED (30)
Ambiguous cases fall to OTHER_PRIVILEGED.
"""
from __future__ import annotations

import pytest
from auditor_schemas.models import PowerCategory
from auditor_core.privilege_map.matchers import (
    BASE_SCORES,
    classify_power,
    match_blacklist_freeze,
    match_burn_others,
    match_change_fee,
    match_change_oracle,
    match_change_parameter,
    match_grant_role,
    match_mint,
    match_other_privileged,
    match_pause,
    match_selfdestruct_or_delegatecall,
    match_upgrade,
    match_withdraw_funds,
)


def test_base_scores_table() -> None:
    assert BASE_SCORES[PowerCategory.SELFDESTRUCT_OR_DELEGATECALL] == 100
    assert BASE_SCORES[PowerCategory.UPGRADE] == 95
    assert BASE_SCORES[PowerCategory.WITHDRAW_FUNDS] == 90
    assert BASE_SCORES[PowerCategory.MINT] == 85
    assert BASE_SCORES[PowerCategory.CHANGE_ORACLE] == 80
    assert BASE_SCORES[PowerCategory.BURN_OTHERS] == 75
    assert BASE_SCORES[PowerCategory.BLACKLIST_FREEZE] == 70
    assert BASE_SCORES[PowerCategory.GRANT_ROLE] == 60
    assert BASE_SCORES[PowerCategory.CHANGE_FEE] == 55
    assert BASE_SCORES[PowerCategory.CHANGE_PARAMETER] == 45
    assert BASE_SCORES[PowerCategory.PAUSE] == 40
    assert BASE_SCORES[PowerCategory.OTHER_PRIVILEGED] == 30


# 1. SELFDESTRUCT_OR_DELEGATECALL
def test_matcher_selfdestruct_or_delegatecall() -> None:
    # Positive: selfdestruct
    pos1 = {"name": "kill", "has_selfdestruct": True}
    matched, facts = match_selfdestruct_or_delegatecall(pos1)
    assert matched is True
    assert facts.get("mechanism") == "selfdestruct"

    # Positive: delegatecall in body
    pos2 = {"name": "exec", "body_source": "target.delegatecall(data);"}
    matched, facts = match_selfdestruct_or_delegatecall(pos2)
    assert matched is True
    assert "delegatecall" in facts.get("mechanism", "")

    # Negative: normal function
    neg = {"name": "transfer", "body_source": "recipient.transfer(amount);"}
    matched, _ = match_selfdestruct_or_delegatecall(neg)
    assert matched is False


# 2. UPGRADE
def test_matcher_upgrade() -> None:
    pos1 = {"name": "_authorizeUpgrade", "body_source": "{}"}
    matched, facts = match_upgrade(pos1)
    assert matched is True
    assert facts.get("upgrade_function") == "_authorizeUpgrade"

    pos2 = {"name": "upgradeToAndCall", "body_source": "{}"}
    matched, _ = match_upgrade(pos2)
    assert matched is True

    neg = {"name": "updateConfig", "body_source": "{}"}
    matched, _ = match_upgrade(neg)
    assert matched is False


# 3. WITHDRAW_FUNDS
def test_matcher_withdraw_funds() -> None:
    pos1 = {"name": "withdrawAll", "body_source": "owner.call{value: balance}('');"}
    matched, facts = match_withdraw_funds(pos1)
    assert matched is True
    assert facts.get("name") == "withdrawAll"

    pos2 = {"name": "emergencyDrain", "body_source": "{}"}
    matched, _ = match_withdraw_funds(pos2)
    assert matched is True

    neg = {"name": "getUserBalance", "body_source": "return balances[msg.sender];"}
    matched, _ = match_withdraw_funds(neg)
    assert matched is False


# 4. MINT
def test_matcher_mint() -> None:
    pos1 = {"name": "mint", "body_source": "totalSupply += amount; balances[to] += amount;"}
    matched, facts = match_mint(pos1)
    assert matched is True
    assert facts.get("mint_function") == "mint"

    pos2 = {"name": "issueTokens", "body_source": "_mint(to, amount);"}
    matched, _ = match_mint(pos2)
    assert matched is True

    neg = {"name": "burn", "body_source": "_burn(msg.sender, amount);"}
    matched, _ = match_mint(neg)
    assert matched is False


# 5. CHANGE_ORACLE
def test_matcher_change_oracle() -> None:
    pos1 = {"name": "setOracle", "body_source": "oracle = newOracle;"}
    matched, facts = match_change_oracle(pos1)
    assert matched is True
    assert facts.get("oracle_function") == "setOracle"

    pos2 = {"name": "updateFeed", "state_writes": ["priceFeedAddress"]}
    matched, _ = match_change_oracle(pos2)
    assert matched is True

    neg = {"name": "setDelay", "state_writes": ["delay"]}
    matched, _ = match_change_oracle(neg)
    assert matched is False


# 6. BURN_OTHERS
def test_matcher_burn_others() -> None:
    pos1 = {"name": "burnFrom", "body_source": "_burn(account, amount);"}
    matched, facts = match_burn_others(pos1)
    assert matched is True
    assert facts.get("burn_function") == "burnFrom"

    pos2 = {"name": "slash", "body_source": "balances[user] -= penalty;"}
    matched, _ = match_burn_others(pos2)
    assert matched is True

    neg = {"name": "burnMyOwn", "body_source": "_burn(msg.sender, amount);"}
    matched, _ = match_burn_others(neg)
    assert matched is False


# 7. BLACKLIST_FREEZE
def test_matcher_blacklist_freeze() -> None:
    pos1 = {"name": "freezeAccount", "body_source": "isFrozen[user] = true;"}
    matched, facts = match_blacklist_freeze(pos1)
    assert matched is True
    assert facts.get("freeze_function") == "freezeAccount"

    pos2 = {"name": "setBlocked", "state_writes": ["blockedUsers"]}
    matched, _ = match_blacklist_freeze(pos2)
    assert matched is True

    neg = {"name": "setRecipient", "state_writes": ["recipient"]}
    matched, _ = match_blacklist_freeze(neg)
    assert matched is False


# 8. GRANT_ROLE
def test_matcher_grant_role() -> None:
    pos1 = {"name": "grantRole", "body_source": "_roles[role][account] = true;"}
    matched, facts = match_grant_role(pos1)
    assert matched is True
    assert facts.get("role_management_function") == "grantRole"

    pos2 = {"name": "transferOwnership", "body_source": "owner = newOwner;"}
    matched, _ = match_grant_role(pos2)
    assert matched is True

    neg = {"name": "deposit", "body_source": "balances[msg.sender] += amount;"}
    matched, _ = match_grant_role(neg)
    assert matched is False


# 9. CHANGE_FEE
def test_matcher_change_fee() -> None:
    pos1 = {"name": "setFee", "body_source": "protocolFee = newFee;"}
    matched, facts = match_change_fee(pos1)
    assert matched is True
    assert facts.get("fee_function") == "setFee"

    pos2 = {"name": "updateRates", "state_writes": ["feeBps"]}
    matched, _ = match_change_fee(pos2)
    assert matched is True

    neg = {"name": "setMaxSupply", "state_writes": ["maxSupply"]}
    matched, _ = match_change_fee(neg)
    assert matched is False


# 10. CHANGE_PARAMETER
def test_matcher_change_parameter() -> None:
    pos1 = {"name": "setLTV", "body_source": "ltv = newLTV;"}
    matched, facts = match_change_parameter(pos1)
    assert matched is True
    assert facts.get("parameter_function") == "setLTV"

    pos2 = {"name": "updateFactor", "state_writes": ["collateralFactor"]}
    matched, _ = match_change_parameter(pos2)
    assert matched is True

    neg = {"name": "getName", "body_source": "return name;"}
    matched, _ = match_change_parameter(neg)
    assert matched is False


# 11. PAUSE
def test_matcher_pause() -> None:
    pos1 = {"name": "pause", "body_source": "paused = true;"}
    matched, facts = match_pause(pos1)
    assert matched is True
    assert facts.get("pause_function") == "pause"

    pos2 = {"name": "setPaused", "state_writes": ["isPaused"]}
    matched, _ = match_pause(pos2)
    assert matched is True

    neg = {"name": "execute", "body_source": "runTask();"}
    matched, _ = match_pause(neg)
    assert matched is False


# 12. OTHER_PRIVILEGED (Fallback)
def test_matcher_other_privileged() -> None:
    ambiguous = {"name": "customGuardedTask", "body_source": "someState = 123;"}
    cat, _ = classify_power(ambiguous)
    assert cat == PowerCategory.OTHER_PRIVILEGED

