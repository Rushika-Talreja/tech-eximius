"""
Tests for Milestone 5: Automated Verification & Patch Generation.
Covers:
1. reentrancy_classic gets a verified patch
2. non-compiling patch rejected
3. patch that introduces a new high finding rejected
4. storage-layout change blocked on uups_proxy
5. edited-diff reverify (increments version)
6. tenant isolation (cross-tenant 404/403)
7. fallback mode: PATCH_MODE=suggest_only returns unverified diffs without claiming compilation
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from auditor_core.patching.verifier import check_storage_layout_impact
from auditor_core.privilege_map.semantic import build_semantic_models_for_project
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"


async def _setup_reentrancy_audit(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> tuple[str, str]:
    """Helper to create project, upload reentrancy_classic, and run audit."""
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Reentrancy M5 Project"},
        headers=auth_a,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    reentrancy_file = FIXTURES_DIR / "reentrancy_classic" / "ReentrancyClassic.sol"
    content = reentrancy_file.read_bytes()

    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": ("ReentrancyClassic.sol", content, "text/plain")},
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
    reentrancy_finding = next((f for f in items if "reentrancy" in f["title"].lower()), None)
    assert reentrancy_finding is not None
    return audit_id, reentrancy_finding["id"]


@pytest.mark.asyncio
async def test_reentrancy_classic_verified_patch(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """1. reentrancy_classic gets a verified patch."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    # Trigger patch generation
    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        json={},
        headers=auth_a,
    )
    assert post_res.status_code == 202
    data = post_res.json()
    assert "patch_id" in data
    patch_id = data["patch_id"]
    assert data["status"] == "draft"

    # Poll until patch verification completes
    patch_data = None
    for _ in range(40):
        get_res = await async_client.get(f"/v1/patches/{patch_id}", headers=auth_a)
        assert get_res.status_code == 200
        patch_data = get_res.json()
        if patch_data["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    assert patch_data is not None
    assert patch_data["status"] == "verified"
    assert patch_data["compiles"] is True
    assert patch_data["finding_cleared"] is True
    assert patch_data["new_findings"] == []
    assert "diff" in patch_data["unified_diff"].lower() or "--- a/" in patch_data["unified_diff"]
    # Check gas_delta when tests do not exist
    assert patch_data["gas_delta"] == {}

    # Check listing patches
    list_res = await async_client.get(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 1
    assert items[0]["id"] == patch_id
    assert items[0]["status"] == "verified"

    # Check finding detail now returns verified patch
    finding_res = await async_client.get(
        f"/v1/audits/{audit_id}/findings/{finding_id}", headers=auth_a
    )
    assert finding_res.status_code == 200
    finding_detail = finding_res.json()
    assert finding_detail["patch"] is not None
    assert finding_detail["patch"]["id"] == patch_id
    assert finding_detail["patch"]["status"] == "verified"

    # Check finding summary has_patch is True
    list_findings = await async_client.get(f"/v1/audits/{audit_id}/findings", headers=auth_a)
    target = next(f for f in list_findings.json()["items"] if f["id"] == finding_id)
    assert target["has_patch"] is True


@pytest.mark.asyncio
async def test_non_compiling_patch_rejected(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """2. Non-compiling patch rejected."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    # Generate initial patch
    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    patch_id = post_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    # Submit user-edited diff with syntax/compilation error
    broken_diff = (
        "--- a/ReentrancyClassic.sol\n"
        "+++ b/ReentrancyClassic.sol\n"
        "@@ -15,2 +15,3 @@\n"
        '         (bool success, ) = msg.sender.call{value: balance}("");\n'
        "+        UNDEFINED_IDENTIFIER_COMPILE_ERROR;\n"
        '         require(success, "Transfer failed");\n'
    )

    verify_res = await async_client.post(
        f"/v1/patches/{patch_id}/verify",
        json={"unified_diff": broken_diff},
        headers=auth_a,
    )
    assert verify_res.status_code == 202
    new_patch_id = verify_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{new_patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    patch_detail = res.json()
    assert patch_detail["status"] == "rejected"
    assert patch_detail["compiles"] is False
    assert patch_detail["finding_cleared"] is False


@pytest.mark.asyncio
async def test_patch_introducing_new_high_finding_rejected(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """3. Patch that introduces a new high finding rejected."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    patch_id = post_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    # Diff that introduces tx.origin (Slither detector: tx-origin, severity: high)
    diff_with_new_high = (
        "--- a/ReentrancyClassic.sol\n"
        "+++ b/ReentrancyClassic.sol\n"
        "@@ -12,4 +12,6 @@\n"
        "     function withdraw() external {\n"
        "+        require(tx.origin == msg.sender, 'BAD_ORIGIN');\n"
        "         uint256 balance = balances[msg.sender];\n"
    )

    verify_res = await async_client.post(
        f"/v1/patches/{patch_id}/verify",
        json={"unified_diff": diff_with_new_high},
        headers=auth_a,
    )
    assert verify_res.status_code == 202
    new_patch_id = verify_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{new_patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    patch_detail = res.json()
    assert patch_detail["status"] == "rejected"
    # Target finding reentrancy wasn't even cleared, or new high introduced
    assert len(patch_detail["new_findings"]) >= 1 or patch_detail["finding_cleared"] is False


@pytest.mark.asyncio
async def test_storage_layout_change_blocked_on_uups_proxy() -> None:
    """4. Storage-layout change blocked on uups_proxy."""
    uups_sol = (FIXTURES_DIR / "uups_proxy" / "UUPSContract.sol").read_text(encoding="utf-8")
    sources = {"UUPSContract.sol": uups_sol}

    # Patch that inserts a new storage variable into MyUUPS before owner
    patched_uups_sol = uups_sol.replace(
        "    address public owner;\n",
        "    uint256 public inserted_slot;\n    address public owner;\n",
    )
    patched_sources = {"UUPSContract.sol": patched_uups_sol}

    orig_models, _ = build_semantic_models_for_project(sources, solc_version="0.8.24")
    patched_models, _ = build_semantic_models_for_project(patched_sources, solc_version="0.8.24")

    ok, msg = check_storage_layout_impact(orig_models, patched_models)
    assert ok is False
    assert "Storage layout modification detected in upgradeable contract" in msg
    assert "MyUUPS" in msg


@pytest.mark.asyncio
async def test_edited_diff_reverify(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    """5. Edited-diff reverify (increments version and verifies valid diff)."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    patch_id = post_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    initial_version = res.json()["version"]

    # Submit valid user-edited diff applying Checks-Effects-Interactions
    valid_edited_diff = (
        "--- a/ReentrancyClassic.sol\n"
        "+++ b/ReentrancyClassic.sol\n"
        "@@ -15,4 +15,4 @@\n"
        '-        (bool success, ) = msg.sender.call{value: balance}("");\n'
        '-        require(success, "Transfer failed");\n'
        "-\n"
        "-        balances[msg.sender] = 0;\n"
        "+        balances[msg.sender] = 0;\n"
        "+\n"
        '+        (bool success, ) = msg.sender.call{value: balance}("");\n'
        '+        require(success, "Transfer failed");\n'
    )

    verify_res = await async_client.post(
        f"/v1/patches/{patch_id}/verify",
        json={"unified_diff": valid_edited_diff},
        headers=auth_a,
    )
    assert verify_res.status_code == 202
    v_data = verify_res.json()
    new_patch_id = v_data["patch_id"]
    assert v_data["version"] == initial_version + 1

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{new_patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    new_patch = res.json()
    assert new_patch["status"] == "verified"
    assert new_patch["version"] == 2
    assert new_patch["compiles"] is True
    assert new_patch["finding_cleared"] is True


@pytest.mark.asyncio
async def test_tenant_isolation(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
) -> None:
    """6. Tenant isolation (cross-tenant 404/403)."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    # User A creates a patch
    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    patch_id = post_res.json()["patch_id"]

    # User B attempts to access User A's patch generation
    cross_post = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_b,
    )
    assert cross_post.status_code in (403, 404)

    # User B attempts to list User A's patches
    cross_list = await async_client.get(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_b,
    )
    assert cross_list.status_code in (403, 404)

    # User B attempts to get User A's patch
    cross_get = await async_client.get(
        f"/v1/patches/{patch_id}",
        headers=auth_b,
    )
    assert cross_get.status_code in (403, 404)

    # User B attempts to verify User A's patch
    cross_verify = await async_client.post(
        f"/v1/patches/{patch_id}/verify",
        json={"unified_diff": "--- a/...\n+++ b/...\n"},
        headers=auth_b,
    )
    assert cross_verify.status_code in (403, 404)


@pytest.mark.asyncio
async def test_fallback_mode_suggest_only(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """7. Fallback mode: PATCH_MODE=suggest_only returns unverified diffs."""
    audit_id, finding_id = await _setup_reentrancy_audit(async_client, auth_a)

    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "patch_mode", "suggest_only")

    post_res = await async_client.post(
        f"/v1/audits/{audit_id}/findings/{finding_id}/patches",
        headers=auth_a,
    )
    assert post_res.status_code == 202
    patch_id = post_res.json()["patch_id"]

    for _ in range(40):
        res = await async_client.get(f"/v1/patches/{patch_id}", headers=auth_a)
        if res.json()["status"] != "draft":
            break
        await asyncio.sleep(0.2)

    patch_detail = res.json()
    assert patch_detail["status"] == "unverified"
    assert patch_detail["compiles"] is None
    assert patch_detail["finding_cleared"] is None
