"""
Unit tests for Privilege Map scoring math, multiplier parameter table,
role escalation, and determinism by shuffling input order.
"""
from __future__ import annotations

import random
import pytest
from auditor_schemas.models import PowerCategory
from auditor_core.privilege_map.scoring import (
    compute_action_score,
    compute_role_scores_with_escalation,
    get_delay_multiplier,
    get_holder_multiplier,
    get_tier,
)


@pytest.mark.parametrize(
    "delay_sec, expected_mult",
    [
        (0, 1.0),
        (1800, 1.0),       # 30m -> 1.0
        (3600, 0.75),      # 1h -> 0.75
        (7200, 0.75),      # 2h -> 0.75
        (86400, 0.5),      # 24h -> 0.5
        (172800, 0.5),     # 48h -> 0.5
    ],
)
def test_delay_multiplier_table(delay_sec: float, expected_mult: float) -> None:
    assert get_delay_multiplier(delay_sec) == expected_mult


@pytest.mark.parametrize(
    "holder_type, threshold, signers, delay_hours, expected_mult, expected_delay_handled",
    [
        (None, None, None, None, 1.0, False),
        ("none", None, None, None, 1.0, False),
        ("eoa", None, None, None, 1.0, False),
        ("contract_unknown", None, None, None, 0.9, False),
        ("multisig", 2, 3, None, 0.7, False),
        ("multisig", 3, 5, None, 0.6, False),
        ("timelock_multisig", 3, 5, 24.0, 0.4, True),
        ("timelock_multisig", 3, 5, 48.0, 0.4, True),
        ("renounced", None, None, None, 0.0, False),
    ],
)
def test_holder_multiplier_table(
    holder_type: str | None,
    threshold: int | None,
    signers: int | None,
    delay_hours: float | None,
    expected_mult: float,
    expected_delay_handled: bool,
) -> None:
    mult, handled = get_holder_multiplier(holder_type, threshold, signers, delay_hours)
    assert mult == expected_mult
    assert handled == expected_delay_handled


def test_action_score_full_formula() -> None:
    # Base: MINT (85), cap present (0.6) -> 51
    score, bd = compute_action_score(
        power_category=PowerCategory.MINT.value,
        mitigations={"cap": {"value": 1000}, "delay_seconds": 0, "reversible": False},
        declaration=None,
    )
    assert score == 51
    assert bd["base"] == 85
    assert bd["cap_mult"] == 0.6
    assert bd["delay_mult"] == 1.0
    assert bd["reversible_mult"] == 1.0
    assert bd["holder_mult"] == 1.0

    # Base: WITHDRAW_FUNDS (90), delay 24h (0.5), reversible (0.85) -> 90 * 0.5 * 0.85 = 38.25 -> 38
    score, bd = compute_action_score(
        power_category=PowerCategory.WITHDRAW_FUNDS.value,
        mitigations={"cap": None, "delay_seconds": 86400, "reversible": True},
        declaration=None,
    )
    assert score == 38
    assert bd["base"] == 90
    assert bd["delay_mult"] == 0.5
    assert bd["reversible_mult"] == 0.85


def test_delay_not_double_counted_with_timelock_multisig() -> None:
    # Declared: timelock_multisig with delay 48h (holder_mult=0.4)
    # in-contract delay 48h
    # Must NOT apply 0.5 delay_mult twice: 90 * 0.4 = 36
    score, bd = compute_action_score(
        power_category=PowerCategory.WITHDRAW_FUNDS.value,
        mitigations={"cap": None, "delay_seconds": 172800, "reversible": False},
        declaration={"holder_type": "timelock_multisig", "threshold": 3, "signers": 5, "delay_hours": 48},
    )
    assert score == 36
    assert bd["holder_mult"] == 0.4
    assert bd["delay_mult"] == 1.0  # Not double counted


def test_role_admin_escalation() -> None:
    # DEFAULT_ADMIN_ROLE administers MINTER_ROLE (action score 85)
    # DEFAULT_ADMIN_ROLE has no direct actions (score 0)
    # Escalation: 0.95 * 85 = 80.75 -> 81
    scores = compute_role_scores_with_escalation(
        role_keys=["DEFAULT_ADMIN_ROLE", "MINTER_ROLE"],
        role_action_scores={"DEFAULT_ADMIN_ROLE": [], "MINTER_ROLE": [85]},
        admin_graph={"DEFAULT_ADMIN_ROLE": ["MINTER_ROLE"]},
        declarations={},
    )
    assert scores["MINTER_ROLE"] == 85
    assert scores["DEFAULT_ADMIN_ROLE"] == 81  # Escalated!


def test_tier_classification() -> None:
    assert get_tier(100) == "critical"
    assert get_tier(80) == "critical"
    assert get_tier(79) == "high"
    assert get_tier(60) == "high"
    assert get_tier(59) == "medium"
    assert get_tier(35) == "medium"
    assert get_tier(34) == "low"
    assert get_tier(1) == "low"
    assert get_tier(0) == "none"


def test_scoring_determinism_shuffled_roles() -> None:
    role_keys = ["OWNER", "DEFAULT_ADMIN_ROLE", "MINTER_ROLE", "PAUSER_ROLE", "CUSTOM:onlyAdmin"]
    action_scores = {
        "OWNER": [90],
        "DEFAULT_ADMIN_ROLE": [],
        "MINTER_ROLE": [85],
        "PAUSER_ROLE": [40],
        "CUSTOM:onlyAdmin": [55],
    }
    admin_graph = {
        "DEFAULT_ADMIN_ROLE": ["MINTER_ROLE", "PAUSER_ROLE"],
        "OWNER": ["DEFAULT_ADMIN_ROLE"],
    }

    base_result = compute_role_scores_with_escalation(
        role_keys=list(role_keys),
        role_action_scores=action_scores,
        admin_graph=admin_graph,
        declarations={},
    )

    for seed in range(20):
        shuffled = list(role_keys)
        random.Random(seed).shuffle(shuffled)
        shuffled_res = compute_role_scores_with_escalation(
            role_keys=shuffled,
            role_action_scores=action_scores,
            admin_graph=admin_graph,
            declarations={},
        )
        assert shuffled_res == base_result

