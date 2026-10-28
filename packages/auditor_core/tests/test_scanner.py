import uuid
import pytest
from auditor_core.detectors.scanner import (
    CandidateFinding,
    CandidateEvidence,
    convert_privilege_candidates_to_findings,
    deduplicate_and_filter_findings,
    run_custom_detectors,
    run_slither_curated_scan,
    load_detector_metadata,
)
from auditor_core.privilege_map.semantic import build_semantic_models_for_project


def test_slither_reentrancy_classic():
    source = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract ReentrancyClassic {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 balance = balances[msg.sender];
        require(balance > 0, "No balance");

        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "Transfer failed");

        balances[msg.sender] = 0;
    }
}
"""
    sources = {"src/ReentrancyClassic.sol": source}
    findings = run_slither_curated_scan(sources, solc_version="0.8.24")
    reentrancy = [f for f in findings if f.detector == "reentrancy-eth"]
    assert len(reentrancy) >= 1
    f = reentrancy[0]
    assert f.source == "slither"
    assert f.severity.lower() == "high"
    assert len(f.evidence) >= 1
    assert f.evidence[0].kind == "static_fact"
    assert f.start_line == 11 or f.start_line == 15


def test_custom_detectors_unprotected_write_and_unbounded_mint():
    source = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract UnprotectedAndUnbounded {
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    function mint(address to, uint256 amount) external {
        totalSupply += amount;
        balanceOf[to] += amount;
    }

    function initialize() external {
        totalSupply = 1000;
    }
}
"""
    sources = {"src/Unprotected.sol": source}
    models, _ = build_semantic_models_for_project(sources, solc_version="0.8.24")

    # Missing AC candidate for mint
    missing_ac = [{
        "contract": "UnprotectedAndUnbounded",
        "function_signature": "mint(address,uint256)",
        "power_category": "MINT",
        "span": {"file": "src/Unprotected.sol", "start_line": 7, "end_line": 10},
        "state_writes": ["totalSupply", "balanceOf"],
    }]

    custom_findings = run_custom_detectors(models, missing_ac)
    detectors = [f.detector for f in custom_findings]

    assert "unprotected-privileged-write" in detectors
    assert "unbounded-mint" in detectors
    assert "missing-initializer-guard" in detectors

    for f in custom_findings:
        assert len(f.evidence) >= 1
        assert f.evidence[0].kind == "static_fact"


def test_deduplication_and_dependency_filtering():
    c1 = CandidateFinding(
        id=uuid.uuid4(),
        source="slither",
        detector="reentrancy-eth",
        category="security",
        title="Reentrancy",
        severity="medium",
        confidence=0.7,
        file_path="src/Vault.sol",
        start_line=10,
        end_line=20,
        description="desc",
        function_signature="withdraw()",
        evidence=[CandidateEvidence(kind="static_fact", title="fact")],
    )
    c2 = CandidateFinding(
        id=uuid.uuid4(),
        source="slither",
        detector="reentrancy-eth",
        category="security",
        title="Reentrancy High",
        severity="high",
        confidence=0.9,
        file_path="src/Vault.sol",
        start_line=10,
        end_line=20,
        description="desc high",
        function_signature="withdraw()",
        evidence=[CandidateEvidence(kind="static_fact", title="fact")],
    )
    c_dep = CandidateFinding(
        id=uuid.uuid4(),
        source="slither",
        detector="tx-origin",
        category="security",
        title="Tx Origin",
        severity="low",
        confidence=0.8,
        file_path="lib/openzeppelin-contracts/Ownable.sol",
        start_line=10,
        end_line=20,
        description="desc dep",
        function_signature="foo()",
        evidence=[CandidateEvidence(kind="static_fact", title="fact")],
    )

    # Exclude dependency by default
    res = deduplicate_and_filter_findings([c1, c2, c_dep], include_dependencies=False)
    assert len(res) == 1
    assert res[0].severity == "high"  # Kept higher severity

    # Include dependency
    res_with_deps = deduplicate_and_filter_findings([c1, c2, c_dep], include_dependencies=True)
    assert len(res_with_deps) == 2


def test_privilege_candidate_conversion():
    candidates = [{
        "role_key": "OWNER",
        "power_category": "WITHDRAW_FUNDS",
        "tier": "critical",
        "blast_score": 90,
        "contract": "Vault",
        "function_signature": "emergencyWithdraw()",
        "facts": {"file_path": "src/Vault.sol", "start_line": 25, "end_line": 30},
        "reason": "Owner can withdraw all funds without delay",
    }]
    findings = convert_privilege_candidates_to_findings(candidates)
    assert len(findings) == 1
    assert findings[0].source == "privilege_map"
    assert findings[0].severity == "critical"
    assert findings[0].evidence[0].kind == "static_fact"

