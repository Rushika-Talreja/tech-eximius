import pytest
from auditor_core.scoring.heuristic import (
    SCORE_LABEL,
    SCORING_WEIGHTS,
    compute_heuristic_scores,
)


def test_clean_contract_scores_100():
    res = compute_heuristic_scores([])
    assert res["overall"] == 100
    assert res["security"] == 100
    assert res["label"] == SCORE_LABEL
    assert res["counts"]["critical"] == 0
    assert res["counts"]["high"] == 0


def test_findings_reduce_score():
    findings = [
        {"severity": "high", "scored": True, "status": "open"},
    ]
    res = compute_heuristic_scores(findings)
    assert res["security"] < 100
    assert res["counts"]["high"] == 1


def test_dismissed_finding_excluded():
    findings = [
        {"severity": "high", "scored": True, "status": "dismissed"},
    ]
    res = compute_heuristic_scores(findings)
    assert res["security"] == 100
    assert res["counts"]["high"] == 0


def test_unscored_finding_excluded():
    findings = [
        {"severity": "critical", "scored": False, "status": "open"},
    ]
    res = compute_heuristic_scores(findings)
    assert res["security"] == 100
    assert res["counts"]["critical"] == 0


def test_privilege_tier_penalty():
    findings = []
    priv = [{"tier": "critical"}]
    res = compute_heuristic_scores(findings, privilege_results=priv)
    assert res["security"] == 100  # Security score only measures finding vulnerabilities
    assert res["overall"] < 100   # Overall score includes privilege tier

