"""
Comprehensive tests for Milestone 6 (Prove-It) and Milestone 7 (Invariants Lite).
Covers:
1. Proof valid and invalid cases:
   - Valid proof: fails on original, passes on patched, twice each -> accepted, stores proof, adds proof evidence, raises confidence, badge proven=True.
   - Invalid proof: passes on original -> rejected.
   - Invalid proof: fails on patched -> rejected.
   - Invalid proof: flaky across runs -> rejected.
   - Invalid proof: trivial test without attacker gain or broken rule assertion -> rejected.
   - Unsupported detector -> rejected.
2. Sandbox egress blocked:
   - Outbound network requests in sandbox environment with allow_network=False are blocked.
3. Feature flags off behavior:
   - PROOFS_ENABLED=false: endpoints return "feature disabled" (422).
   - INVARIANTS_ENABLED=false: endpoints return "feature disabled" (422).
   - Audit creation with disabled features rejected with "feature disabled".
4. Invariant template violations on vulnerable and clean fixtures:
   - erc4626_vulnerable violates previewRedeem(previewDeposit(x)) <= x -> violated, stores minimal call sequence, creates finding with proof evidence.
   - erc4626_clean passes -> passed.
   - Contract type classification confidence and user override.
   - Non-applicable templates skipped with reason.
5. Exports:
   - Exploit tests are NOT included in default exports (only when include_tests=True).
6. Rate limiting:
   - Proof generation endpoint enforces rate limits.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import get_settings
from auditor_core.invariants.classifier import classify_contract_type_with_confidence
from auditor_core.invariants.loader import load_invariant_templates
from auditor_core.proofs.drafter import (
    is_detector_supported,
    validate_test_asserts_rule_or_gain,
)
from auditor_core.proofs.verifier import verify_proof_test
from auditor_core.sandbox.runner import SandboxRunner

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"


# ─── 1. Flag-Off Behavior Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feature_flags_off_behavior(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """When PROOFS_ENABLED and INVARIANTS_ENABLED are False, endpoints return 'feature disabled'."""
    settings = get_settings()
    settings.proofs_enabled = False
    settings.invariants_enabled = False

    fake_id = "00000000-0000-0000-0000-000000000001"

    # 1. Proof endpoints
    proof_post = await async_client.post(
        f"/v1/audits/{fake_id}/findings/{fake_id}/proof",
        headers=auth_a,
    )
    assert proof_post.status_code == 422
    assert "disabled" in proof_post.json()["error"]["message"].lower()

    proof_get = await async_client.get(
        f"/v1/findings/{fake_id}/proof",
        headers=auth_a,
    )
    assert proof_get.status_code == 422
    assert "disabled" in proof_get.json()["error"]["message"].lower()

    proofs_list = await async_client.get(
        f"/v1/audits/{fake_id}/proofs",
        headers=auth_a,
    )
    assert proofs_list.status_code == 422
    assert "disabled" in proofs_list.json()["error"]["message"].lower()

    # 2. Invariant endpoints
    inv_post = await async_client.post(
        f"/v1/audits/{fake_id}/invariant-runs",
        headers=auth_a,
    )
    assert inv_post.status_code == 422
    assert "disabled" in inv_post.json()["error"]["message"].lower()

    inv_get = await async_client.get(
        f"/v1/audits/{fake_id}/invariant-runs",
        headers=auth_a,
    )
    assert inv_get.status_code == 422
    assert "disabled" in inv_get.json()["error"]["message"].lower()

    # 3. Audit creation with disabled features
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Flags Off Project"},
        headers=auth_a,
    )
    proj_id = proj_resp.json()["id"]

    audit_resp = await async_client.post(
        f"/v1/projects/{proj_id}/audits",
        json={
            "upload_id": fake_id,
            "options": {"features": ["proofs"]},
        },
        headers=auth_a,
    )
    assert audit_resp.status_code == 422
    assert "disabled" in audit_resp.json()["error"]["message"].lower()


# ─── 2. Sandbox Egress Blocked Test ───────────────────────────────────────────


def test_sandbox_egress_blocked() -> None:
    """Outbound network requests in sandbox environment with allow_network=False are blocked."""
    runner = SandboxRunner(runtime="local", timeout_seconds=10)
    clean_env = runner._prepare_clean_env(allow_network=False)

    # Proxies must point to blackhole 127.0.0.1:0
    assert clean_env.get("HTTP_PROXY") == "http://127.0.0.1:0"
    assert clean_env.get("HTTPS_PROXY") == "http://127.0.0.1:0"
    assert clean_env.get("ALL_PROXY") == "socks5://127.0.0.1:0"

    # Command verifying outbound network failure
    py_code = (
        "import urllib.request, os; "
        "opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': os.environ.get('HTTP_PROXY')} if os.environ.get('HTTP_PROXY') else {})); "
        "urllib.request.install_opener(opener); "
        "urllib.request.urlopen('http://example.com', timeout=2)"
    )
    res = runner.run(["python3", "-c", py_code], allow_network=False)
    # Network request must fail or exit with non-zero
    assert res.exit_code != 0


# ─── 3. Proof Verifier Valid & Invalid Cases ──────────────────────────────────


def test_proof_verifier_validation_cases() -> None:
    """Test validation of proof test drafts (assertions of attacker gain or broken rule)."""
    # 1. Trivial test without assertions
    trivial_test = "contract TrivialTest { function test_pass() public {} }"
    valid, err = validate_test_asserts_rule_or_gain(trivial_test)
    assert not valid
    assert "no assertions" in err.lower()

    # 2. Test with assertion but no attacker gain or rule break
    no_rule_test = "contract GenericTest { function test_something() public { assertTrue(true); } }"
    valid, err = validate_test_asserts_rule_or_gain(no_rule_test)
    assert not valid
    assert "attacker gain or broken security rule" in err.lower()

    # 3. Valid test asserting victim balance preserved (attacker gain rule)
    valid_test = (
        "contract ExploitTest { "
        "  function test_exploit_cannot_drain() public { "
        "    uint256 victimBalance = 10; "
        "    assertTrue(victimBalance > 0, 'Attacker drained victim balance'); "
        "  } "
        "}"
    )
    valid, err = validate_test_asserts_rule_or_gain(valid_test)
    assert valid
    assert err == ""


def test_proof_verifier_execution_cases() -> None:
    """Test verify_proof_test logic across original, patched, flaky, and trivial scenarios."""
    test_src = (
        "contract ExploitTest { "
        "  function test_exploit_cannot_drain() public { "
        "    assertTrue(true, 'Attacker balance drain rule'); "
        "  } "
        "}"
    )
    orig_src = {"ReentrancyClassic.sol": "contract ReentrancyClassic { balances[msg.sender] = 0; .call; balances[msg.sender] = 0; }"}
    patched_src = {"ReentrancyClassic.sol": "contract ReentrancyClassic { balances[msg.sender] = 0; .call; }"}

    # 1. Valid proof: fails on original, passes on patched, run twice
    res = verify_proof_test(
        test_source=test_src,
        original_sources={"ReentrancyClassic.sol": "contract ReentrancyClassic { balances[msg.sender] = 10; .call; balances[msg.sender] = 0; }"},
        patched_sources=patched_src,
    )
    assert res.accepted is True
    assert res.fails_on_original is True
    assert res.passes_on_patched is True

    # 2. Invalid: passes on original
    res_pass_orig = verify_proof_test(
        test_source=test_src,
        original_sources=orig_src,
        patched_sources=patched_src,
        always_pass_mode=True,
    )
    assert res_pass_orig.accepted is False
    assert "passed on original" in res_pass_orig.rejection_reason.lower()

    # 3. Invalid: fails on patched
    res_fail_patch = verify_proof_test(
        test_source=test_src,
        original_sources={"ReentrancyClassic.sol": "contract ReentrancyClassic { balances[msg.sender] = 10; .call; balances[msg.sender] = 0; }"},
        patched_sources=patched_src,
        always_fail_mode=True,
    )
    assert res_fail_patch.accepted is False
    assert "failed on verified patch" in res_fail_patch.rejection_reason.lower()

    # 4. Invalid: flaky test
    res_flaky = verify_proof_test(
        test_source=test_src,
        original_sources={"ReentrancyClassic.sol": "contract ReentrancyClassic { balances[msg.sender] = 10; .call; balances[msg.sender] = 0; }"},
        patched_sources=patched_src,
        flaky_mode=True,
    )
    assert res_flaky.accepted is False
    assert "flaky" in res_flaky.rejection_reason.lower()


def test_supported_detectors_filtering() -> None:
    """Verify supported vs unsupported detectors for M6."""
    assert is_detector_supported("reentrancy-eth")[0] is True
    assert is_detector_supported("missing-access-control")[0] is True
    assert is_detector_supported("unchecked-low-level-call")[0] is True
    assert is_detector_supported("oracle-read")[0] is True

    # Unsupported
    assert is_detector_supported("solc-version")[0] is False
    assert is_detector_supported("naming-convention")[0] is False


# ─── 4. End-to-End M6 Proof Generation Test ───────────────────────────────────


async def _setup_audit_with_finding(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    fixture_folder: str,
    fixture_filename: str,
) -> tuple[str, str]:
    """Helper to create project, upload contract, and run audit."""
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": f"Audit {fixture_folder}"},
        headers=auth_a,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    sol_path = FIXTURES_DIR / fixture_folder / fixture_filename
    content = sol_path.read_bytes()

    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": (fixture_filename, content, "text/plain")},
        headers=auth_a,
    )
    assert upload_resp.status_code == 201
    upload_id = upload_resp.json()["upload_id"]

    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_id = audit_resp.json()["audit_id"]

    for _ in range(40):
        get_audit = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_audit.json()["status"] == "complete":
            break
        await asyncio.sleep(0.2)

    assert get_audit.json()["status"] == "complete"

    findings_resp = await async_client.get(f"/v1/audits/{audit_id}/findings", headers=auth_a)
    assert findings_resp.status_code == 200
    items = findings_resp.json()["items"]
    assert len(items) > 0
    return audit_id, items[0]["id"]


@pytest.mark.asyncio
async def test_reentrancy_classic_proof_generation_flow(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """
    Test end-to-end M6 Prove-It flow:
    - Generates proof for reentrancy_classic finding
    - Validates fails_on_original=True and passes_on_patched=True
    - Verifies proof evidence added and confidence raised
    - Verifies badge proven=True
    - Verifies test not in default export
    """
    settings = get_settings()
    settings.proofs_enabled = True

    audit_id, finding_id = await _setup_audit_with_finding(
        async_client, auth_a, "reentrancy_classic", "ReentrancyClassic.sol"
    )

    # 1. Trigger Proof Generation
    proof_post = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/proof",
        headers=auth_a,
    )
    if proof_post.status_code != 202:
        print("PROOF_POST_ERROR:", proof_post.status_code, proof_post.json())
    assert proof_post.status_code == 202
    post_data = proof_post.json()
    assert "proof_id" in post_data
    assert post_data["status"] == "verified"
    proof_id = post_data["proof_id"]

    # 2. Get proof by finding
    proof_get = await async_client.get(
        f"/v1/findings/{finding_id}/proof",
        headers=auth_a,
    )
    assert proof_get.status_code == 200
    proof_data = proof_get.json()
    assert proof_data["id"] == proof_id
    assert proof_data["fails_on_original"] is True
    assert proof_data["passes_on_patched"] is True
    assert "assert" in proof_data["test_source"].lower()

    # 3. Check finding has proof evidence, raised confidence, and proven=True
    finding_get = await async_client.get(
        f"/v1/audits/{audit_id}/findings/{finding_id}",
        headers=auth_a,
    )
    assert finding_get.status_code == 200
    f_json = finding_get.json()
    assert f_json["proof"] is not None
    assert f_json["proof"]["id"] == proof_id
    evidence_kinds = [e["kind"] for e in f_json["evidence"]]
    assert "proof" in evidence_kinds
    assert float(f_json["confidence"]) >= 0.95

    # Check finding summary badge proven=True
    list_res = await async_client.get(
        f"/v1/audits/{audit_id}/findings",
        headers=auth_a,
    )
    summaries = list_res.json()["items"]
    target_summary = next(s for s in summaries if s["id"] == finding_id)
    assert target_summary["proven"] is True

    # 4. Check exports: proof test is NOT in default export
    default_export = await async_client.get(
        f"/v1/audits/{audit_id}/export?format=json",
        headers=auth_a,
    )
    assert default_export.status_code == 200
    exp_json = default_export.json()
    finding_exp = next(f for f in exp_json["findings"] if f["id"] == finding_id)
    assert "test_source" not in finding_exp

    # Export with include_tests=True includes the test source
    opted_export = await async_client.get(
        f"/v1/audits/{audit_id}/export?format=json&include_tests=true",
        headers=auth_a,
    )
    assert opted_export.status_code == 200
    opt_json = opted_export.json()
    opt_finding = next(f for f in opt_json["findings"] if f["id"] == finding_id)
    assert "test_source" in opt_finding


# ─── 5. M7 Invariant Templates & Classification Tests ─────────────────────────


def test_invariant_classifier_and_templates() -> None:
    """Test contract type classification confidence and template discovery."""
    # 1. ERC4626 classification
    c_type, conf = classify_contract_type_with_confidence(
        function_names={"asset", "totalAssets", "previewDeposit", "previewRedeem", "deposit"},
        inheritance=["ERC4626"],
    )
    assert c_type == "erc4626"
    assert conf >= 0.9

    # 2. User override
    c_type_ov, conf_ov = classify_contract_type_with_confidence(
        function_names={"someRandomFunction"},
        inheritance=[],
        override="erc4626",
    )
    assert c_type_ov == "erc4626"
    assert conf_ov == 1.0

    # 3. Template loader
    templates = load_invariant_templates()
    assert len(templates) >= 10
    categories = {t.category for t in templates}
    assert {"erc20", "erc4626", "staking", "lending"}.issubset(categories)

    # Every template has id, description, applies_if
    for t in templates:
        assert t.id != ""
        assert t.description != ""
        assert t.applies_if != ""


# ─── 6. M7 Invariants on Vulnerable vs Clean Fixtures ─────────────────────────


@pytest.mark.asyncio
async def test_invariant_runs_vulnerable_and_clean_fixtures(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """
    Test M7 invariant execution on:
    1. erc4626_vulnerable -> violates previewRedeem(previewDeposit(x)) <= x
       - Status violated
       - Minimal call sequence counterexample recorded
       - New finding created with proof evidence
    2. erc4626_clean -> passes all invariants
       - Status passed
    """
    settings = get_settings()
    settings.invariants_enabled = True

    # ── Test 1: erc4626_vulnerable ──
    vuln_audit_id, _ = await _setup_audit_with_finding(
        async_client, auth_a, "erc4626_vulnerable", "ERC4626Vulnerable.sol"
    )

    vuln_run_resp = await async_client.post(
        f"/v1/audits/{vuln_audit_id}/invariant-runs",
        json={"templates": ["all"]},
        headers=auth_a,
    )
    assert vuln_run_resp.status_code == 202
    assert "run_group_id" in vuln_run_resp.json()

    # Get invariant runs
    runs_res = await async_client.get(
        f"/v1/audits/{vuln_audit_id}/invariant-runs",
        headers=auth_a,
    )
    assert runs_res.status_code == 200
    runs = runs_res.json()["items"]
    assert len(runs) > 0

    # Locate preview_redeem_deposit run
    preview_run = next(r for r in runs if r["template_id"] == "erc4626_preview_redeem_deposit")
    assert preview_run["status"] == "violated"
    assert preview_run["counterexample"] is not None
    assert len(preview_run["counterexample"]["sequence"]) == 2

    # Check invariant finding created with proof evidence
    findings_res = await async_client.get(
        f"/v1/audits/{vuln_audit_id}/findings",
        headers=auth_a,
    )
    f_items = findings_res.json()["items"]
    inv_finding = next((f for f in f_items if f["source"] == "invariant"), None)
    assert inv_finding is not None
    assert "erc4626_preview_redeem_deposit" in inv_finding["title"]

    inv_f_detail = await async_client.get(
        f"/v1/audits/{vuln_audit_id}/findings/{inv_finding['id']}",
        headers=auth_a,
    )
    ev_kinds = [e["kind"] for e in inv_f_detail.json()["evidence"]]
    assert "proof" in ev_kinds

    # ── Test 2: erc4626_clean ──
    clean_audit_id, _ = await _setup_audit_with_finding(
        async_client, auth_a, "erc4626_clean", "ERC4626Clean.sol"
    )

    clean_run_resp = await async_client.post(
        f"/v1/audits/{clean_audit_id}/invariant-runs",
        json={"templates": ["all"]},
        headers=auth_a,
    )
    assert clean_run_resp.status_code == 202

    clean_runs_res = await async_client.get(
        f"/v1/audits/{clean_audit_id}/invariant-runs",
        headers=auth_a,
    )
    clean_runs = clean_runs_res.json()["items"]
    clean_preview = next(r for r in clean_runs if r["template_id"] == "erc4626_preview_redeem_deposit")
    assert clean_preview["status"] == "passed"
    assert clean_preview["counterexample"] is None


# ─── 7. Rate Limiting Test ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proof_endpoint_rate_limiting(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """Hammering the proof generation endpoint exceeds limit and returns 429."""
    settings = get_settings()
    settings.proofs_enabled = True

    audit_id, finding_id = await _setup_audit_with_finding(
        async_client, auth_a, "reentrancy_classic", "ReentrancyClassic.sol"
    )

    # Make 12 rapid calls (limit is 10)
    rate_limited_hit = False
    for _ in range(12):
        resp = await async_client.post(
            f"/v1/audits/{audit_id}/findings/{finding_id}/proof",
            headers=auth_a,
        )
        if resp.status_code == 429:
            rate_limited_hit = True
            assert "RATE_LIMITED" in resp.json()["error"]["code"]
            break

    assert rate_limited_hit is True

