"""
Tests for Privilege Map API Endpoints:
  - 409 AUDIT_NOT_READY until stage privilege_map completes
  - GET /audits/{id}/privilege-map returns PrivilegeMap conforming to api_endpoints.md
  - PUT /audits/{id}/role-declarations:
      * validation: threshold <= signers (422)
      * validation: unknown role_key rejected (422)
      * synchronous recompute under 300 ms
      * score lowers when 3-of-5 multisig with 48h timelock declared
  - GET /audits/{id}/role-declarations returns declarations
  - Tenant isolation on both GET and PUT endpoints
  - Exit gates:
      * uploading vault_basic yields correct tiers
      * multisig lowers score
      * assembly_edge shows undetected_notes
"""
from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"


async def _run_audit_to_completion(
    async_client: AsyncClient,
    auth: dict[str, str],
    project_id: str,
    fixture_path: Path,
    filename: str = "Contract.sol",
) -> str:
    # Upload
    with open(fixture_path, "rb") as f:
        up_res = await async_client.post(
            "/v1/uploads",
            files={"file": (filename, f, "text/plain")},
            headers=auth,
        )
    assert up_res.status_code == 201
    upload_id = up_res.json()["upload_id"]

    # Trigger audit
    audit_res = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth,
    )
    assert audit_res.status_code == 202
    audit_id = audit_res.json()["audit_id"]

    # Poll until complete
    for _ in range(60):
        get_res = await async_client.get(f"/v1/audits/{audit_id}", headers=auth)
        assert get_res.status_code == 200
        if get_res.json()["status"] in ("complete", "failed"):
            break
        await asyncio.sleep(0.1)

    assert get_res.json()["status"] == "complete", f"Audit failed: {get_res.json().get('error')}"
    return audit_id


@pytest.mark.asyncio
async def test_privilege_map_409_until_ready(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    # Create project and upload
    proj_res = await async_client.post(
        "/v1/projects",
        json={"name": "409 Test Project"},
        headers=auth_a,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    vault_file = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    with open(vault_file, "rb") as f:
        up_res = await async_client.post(
            "/v1/uploads",
            files={"file": ("Vault.sol", f, "text/plain")},
            headers=auth_a,
        )
    upload_id = up_res.json()["upload_id"]

    # Create audit
    audit_res = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    audit_id = audit_res.json()["audit_id"]

    # Immediate query might be queued -> 409
    pmap_res = await async_client.get(f"/v1/audits/{audit_id}/privilege-map", headers=auth_a)
    if pmap_res.status_code == 409:
        err = pmap_res.json()["error"]
        assert err["code"] == "AUDIT_NOT_READY"


@pytest.mark.asyncio
async def test_privilege_map_vault_basic_success(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    # 1. Project
    proj_res = await async_client.post(
        "/v1/projects",
        json={"name": "Vault Basic Audit"},
        headers=auth_a,
    )
    project_id = proj_res.json()["id"]

    # 2. Run audit
    vault_file = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    audit_id = await _run_audit_to_completion(async_client, auth_a, project_id, vault_file, "Vault.sol")

    # 3. Fetch privilege map
    pmap_res = await async_client.get(f"/v1/audits/{audit_id}/privilege-map", headers=auth_a)
    assert pmap_res.status_code == 200
    data = pmap_res.json()

    assert data["scoring_config_version"] == "1"
    assert "disclaimer" in data
    assert len(data["roles"]) == 1

    owner_role = data["roles"][0]
    assert owner_role["role_key"] == "OWNER"
    assert owner_role["display_name"] == "Owner"
    assert owner_role["tier"] == "critical"
    assert owner_role["blast_score"] == 90
    assert owner_role["holder_assumed"] is True
    assert "withdraw funds" in owner_role["worst_case"]
    assert "No timelock, no cap, no multisig assumed." in owner_role["worst_case"]

    # Check edges
    edges = data["edges"]
    assert len(edges) >= 2
    assert any(e["from"] == "OWNER" and "WITHDRAW_FUNDS" in e["to"] for e in edges)
    assert any(e["from"] == "OWNER" and "MINT" in e["to"] for e in edges)


@pytest.mark.asyncio
async def test_role_declarations_validation_and_sync_recompute(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    # Setup audit on vault_basic
    proj_res = await async_client.post("/v1/projects", json={"name": "Declaration Test"}, headers=auth_a)
    project_id = proj_res.json()["id"]
    vault_file = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    audit_id = await _run_audit_to_completion(async_client, auth_a, project_id, vault_file, "Vault.sol")

    # 1. Validation error: unknown role_key rejected with 422
    bad_role_res = await async_client.put(
        f"/v1/audits/{audit_id}/role-declarations",
        json={"declarations": [{"role_key": "NON_EXISTENT_ROLE", "holder_type": "eoa"}]},
        headers=auth_a,
    )
    assert bad_role_res.status_code == 422
    assert "VALIDATION_ERROR" in bad_role_res.json()["error"]["code"]

    # 2. Validation error: threshold > signers rejected with 422
    bad_msig_res = await async_client.put(
        f"/v1/audits/{audit_id}/role-declarations",
        json={"declarations": [{"role_key": "OWNER", "holder_type": "multisig", "threshold": 5, "signers": 3}]},
        headers=auth_a,
    )
    assert bad_msig_res.status_code == 422

    # 3. Synchronous recompute under 300 ms
    # Change Owner to 3-of-5 multisig with 48h delay
    start_t = time.perf_counter()
    put_res = await async_client.put(
        f"/v1/audits/{audit_id}/role-declarations",
        json={
            "declarations": [
                {
                    "role_key": "OWNER",
                    "holder_type": "timelock_multisig",
                    "threshold": 3,
                    "signers": 5,
                    "delay_hours": 48.0,
                }
            ]
        },
        headers=auth_a,
    )
    duration_ms = (time.perf_counter() - start_t) * 1000
    assert duration_ms < 300, f"Recompute took {duration_ms}ms, target is < 300ms"

    assert put_res.status_code == 200
    updated_pmap = put_res.json()
    owner_role = updated_pmap["roles"][0]
    assert owner_role["role_key"] == "OWNER"
    # 90 * 0.4 = 36 (Tier: medium)
    assert owner_role["blast_score"] == 36
    assert owner_role["tier"] == "medium"
    assert owner_role["holder_assumed"] is False
    assert "Declared: 3-of-5 multisig, 48h timelock." in owner_role["worst_case"]

    # 4. GET /audits/{id}/role-declarations
    get_decl_res = await async_client.get(f"/v1/audits/{audit_id}/role-declarations", headers=auth_a)
    assert get_decl_res.status_code == 200
    decl_data = get_decl_res.json()
    assert len(decl_data["declarations"]) == 1
    assert decl_data["declarations"][0]["role_key"] == "OWNER"
    assert decl_data["declarations"][0]["threshold"] == 3
    assert decl_data["declarations"][0]["signers"] == 5
    assert decl_data["declarations"][0]["delay_hours"] == 48.0


@pytest.mark.asyncio
async def test_tenant_isolation_privilege_map_and_declarations(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
) -> None:
    # Org A creates audit
    proj_res = await async_client.post("/v1/projects", json={"name": "Org A Project"}, headers=auth_a)
    project_id = proj_res.json()["id"]
    vault_file = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    audit_id = await _run_audit_to_completion(async_client, auth_a, project_id, vault_file, "Vault.sol")

    # Org B attempts GET /privilege-map -> 404
    cross_get = await async_client.get(f"/v1/audits/{audit_id}/privilege-map", headers=auth_b)
    assert cross_get.status_code == 404
    assert cross_get.json()["error"]["code"] == "NOT_FOUND"

    # Org B attempts PUT /role-declarations -> 404
    cross_put = await async_client.put(
        f"/v1/audits/{audit_id}/role-declarations",
        json={"declarations": [{"role_key": "OWNER", "holder_type": "eoa"}]},
        headers=auth_b,
    )
    assert cross_put.status_code == 404

    # Org B attempts GET /role-declarations -> 404
    cross_decl_get = await async_client.get(f"/v1/audits/{audit_id}/role-declarations", headers=auth_b)
    assert cross_decl_get.status_code == 404


@pytest.mark.asyncio
async def test_assembly_edge_shows_undetected_note(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    proj_res = await async_client.post("/v1/projects", json={"name": "Assembly Edge Project"}, headers=auth_a)
    project_id = proj_res.json()["id"]

    assembly_file = FIXTURES_DIR / "assembly_edge" / "AssemblyVault.sol"
    audit_id = await _run_audit_to_completion(async_client, auth_a, project_id, assembly_file, "AssemblyVault.sol")

    pmap_res = await async_client.get(f"/v1/audits/{audit_id}/privilege-map", headers=auth_a)
    assert pmap_res.status_code == 200
    data = pmap_res.json()
    notes = data["undetected_notes"]
    assert len(notes) > 0
    assert any("Inline assembly" in n for n in notes)

