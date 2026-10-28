"""
End-to-End Integration Verification: M0, M1, M2, and M3.
Tests that all components across foundations, ingestion/build, semantic model & privilege map,
and static findings & reporting work together in a unified workflow.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from auditor_schemas.constants import STANDARD_DISCLAIMER


@pytest.mark.asyncio
async def test_m0_to_m3_full_integration(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
) -> None:
    # ─── M0: Foundations & Health & Auth ──────────────────────────────────────
    health_res = await async_client.get("/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    me_res = await async_client.get("/v1/me", headers=auth_a)
    assert me_res.status_code == 200
    user_data = me_res.json()
    assert "user" in user_data and "org" in user_data

    # API key generation & authentication
    key_res = await async_client.post(
        "/v1/api-keys",
        json={"name": "Integration Key", "scopes": ["audits:write", "audits:read"]},
        headers=auth_a,
    )
    assert key_res.status_code == 201
    api_key_data = key_res.json()
    raw_api_key = api_key_data["key"]
    api_key_auth = {"X-API-Key": raw_api_key}

    # ─── M1: Ingestion, Build, and Storage ────────────────────────────────────
    proj_res = await async_client.post(
        "/v1/projects",
        json={"name": "M0-M3 Vault Protocol", "description": "End-to-end audit"},
        headers=api_key_auth,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    vault_file = Path("fixtures/contracts/vault_basic/Vault.sol")
    assert vault_file.exists()
    content = vault_file.read_bytes()

    upload_res = await async_client.post(
        "/v1/uploads",
        files={"file": ("Vault.sol", content, "text/plain")},
        headers=api_key_auth,
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["upload_id"]

    audit_res = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id, "options": {"solc_version": "0.8.24"}},
        headers=api_key_auth,
    )
    assert audit_res.status_code == 202
    audit_data = audit_res.json()
    audit_id = audit_data["audit_id"]
    events_url = audit_data["events_url"]

    # Wait for the pipeline to finish through all stages
    for _ in range(40):
        get_audit = await async_client.get(f"/v1/audits/{audit_id}", headers=api_key_auth)
        if get_audit.json()["status"] in ("complete", "failed"):
            break
        await pytest.importorskip("asyncio").sleep(0.5)

    audit_detail = get_audit.json()
    assert audit_detail["status"] == "complete", f"Audit failed: {audit_detail.get('error')}"
    assert audit_detail["stage"] == "reporting"
    assert audit_detail["compiler_version"] == "0.8.24"
    assert "solc" in audit_detail["toolchain"]

    # Verify M1 file listing and contents
    files_res = await async_client.get(f"/v1/audits/{audit_id}/files", headers=api_key_auth)
    assert files_res.status_code == 200
    files_list = files_res.json()["items"]
    assert len(files_list) >= 1
    file_id = files_list[0]["id"]

    file_content_res = await async_client.get(f"/v1/audits/{audit_id}/files/{file_id}", headers=api_key_auth)
    assert file_content_res.status_code == 200
    assert "contract SimpleVault" in file_content_res.json()["content"]

    # Verify M1 SSE events emitted across stages
    events_res = await async_client.get(events_url, headers=api_key_auth)
    assert events_res.status_code == 200
    events_text = events_res.text
    assert "event: stage_started" in events_text
    assert "event: privilege_map_ready" in events_text
    assert "event: stage_completed" in events_text
    assert "event: audit_completed" in events_text

    # ─── M2: Semantic Model and Privilege Map ─────────────────────────────────
    pmap_res = await async_client.get(f"/v1/audits/{audit_id}/privilege-map", headers=api_key_auth)
    assert pmap_res.status_code == 200
    pmap_data = pmap_res.json()
    assert "roles" in pmap_data
    assert pmap_data["scoring_config_version"] is not None

    owner_role = next((r for r in pmap_data["roles"] if r["role_key"] == "OWNER"), None)
    assert owner_role is not None
    initial_owner_score = owner_role["blast_score"]
    assert initial_owner_score > 0

    # Role declaration update & synchronous recompute
    t_start = time.perf_counter()
    decl_res = await async_client.put(
        f"/v1/audits/{audit_id}/role-declarations",
        json={
            "declarations": [
                {
                    "role_key": "OWNER",
                    "holder_type": "timelock_multisig",
                    "threshold": 3,
                    "signers": 5,
                    "delay_seconds": 172800,  # 48h
                }
            ]
        },
        headers=api_key_auth,
    )
    duration_ms = (time.perf_counter() - t_start) * 1000
    assert decl_res.status_code == 200
    assert duration_ms < 500  # fast recompute under 500 ms

    updated_pmap = decl_res.json()
    updated_owner = next(r for r in updated_pmap["roles"] if r["role_key"] == "OWNER")
    assert updated_owner["blast_score"] < initial_owner_score
    assert "Declared: 3-of-5 multisig" in updated_owner["worst_case"]

    # ─── M3: Static Findings, Coverage Statement, Heuristic Scoring, Exports ──
    # Coverage statement
    coverage = audit_detail["coverage"]
    assert "SimpleVault" in coverage["analyzed"]["contracts"]
    assert "economic design" in coverage["out_of_scope"]
    assert len(coverage["analyzed"]["detectors_run"]) >= 15

    # Heuristic scoring
    scores = audit_detail["scores"]
    assert scores["label"] == "heuristic risk indicator"
    assert "security" in scores
    assert "overall" in scores
    assert "weights" in scores

    # Findings list
    findings_res = await async_client.get(f"/v1/audits/{audit_id}/findings", headers=api_key_auth)
    assert findings_res.status_code == 200
    findings = findings_res.json()["items"]
    assert len(findings) >= 1

    first_finding = findings[0]
    fid = first_finding["id"]

    # Finding detail
    fdetail_res = await async_client.get(f"/v1/audits/{audit_id}/findings/{fid}", headers=api_key_auth)
    assert fdetail_res.status_code == 200
    fdetail = fdetail_res.json()
    assert len(fdetail["spans"]) >= 1
    assert len(fdetail["evidence"]) >= 1
    assert fdetail["evidence"][0]["kind"] == "static_fact"
    assert fdetail["disclaimer"] == STANDARD_DISCLAIMER

    # Dismiss finding -> recomputes score synchronously
    patch_res = await async_client.patch(
        f"/v1/audits/{audit_id}/findings/{fid}",
        json={"status": "dismissed", "reason": "verified acceptable risk"},
        headers=api_key_auth,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "dismissed"

    # Export formats
    export_json = await async_client.get(f"/v1/audits/{audit_id}/export?format=json", headers=api_key_auth)
    assert export_json.status_code == 200
    assert "attachment" in export_json.headers["Content-Disposition"]
    assert export_json.json()["disclaimer"] == STANDARD_DISCLAIMER

    export_md = await async_client.get(f"/v1/audits/{audit_id}/export?format=md", headers=api_key_auth)
    assert export_md.status_code == 200
    assert "Coverage Statement" in export_md.text

    export_sarif = await async_client.get(f"/v1/audits/{audit_id}/export?format=sarif", headers=api_key_auth)
    assert export_sarif.status_code == 200
    assert export_sarif.json()["version"] == "2.1.0"

    # ─── Cross-Cutting: Multi-Tenant Isolation on All Resources ───────────────
    for cross_url in [
        f"/v1/projects/{project_id}",
        f"/v1/audits/{audit_id}",
        f"/v1/audits/{audit_id}/files",
        f"/v1/audits/{audit_id}/files/{file_id}",
        f"/v1/audits/{audit_id}/privilege-map",
        f"/v1/audits/{audit_id}/findings",
        f"/v1/audits/{audit_id}/findings/{fid}",
        f"/v1/audits/{audit_id}/export?format=json",
    ]:
        b_res = await async_client.get(cross_url, headers=auth_b)
        assert b_res.status_code in (403, 404), f"Failed tenant isolation for {cross_url}: got {b_res.status_code}"

    # ─── M1: Immediate Purge Deletion ─────────────────────────────────────────
    del_res = await async_client.delete(f"/v1/audits/{audit_id}", headers=api_key_auth)
    assert del_res.status_code == 204

    # Purged audit returns 410 AUDIT_PURGED
    purged_res = await async_client.get(f"/v1/audits/{audit_id}", headers=api_key_auth)
    assert purged_res.status_code == 410
    assert purged_res.json()["error"]["code"] == "AUDIT_PURGED"

