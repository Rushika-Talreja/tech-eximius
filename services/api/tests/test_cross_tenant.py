"""
Cross-tenant isolation tests.
User B cannot access, list, or delete User A's projects or audits.
DB-level RLS verification ensures org isolation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import _provision_user, set_rls_org
from app.config import get_settings
from app.db import Audit, Organization, Project, Upload, User


@pytest.mark.asyncio
async def test_cross_tenant_project_isolation(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
    db_session: AsyncSession,
) -> None:
    # 1. User A creates a project
    create_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Org A Confidential Protocol", "description": "Vault contracts"},
        headers=auth_a,
    )
    assert create_resp.status_code == 201, create_resp.text
    project_a = create_resp.json()
    project_id = project_a["id"]

    # 2. User B cannot read User A's project
    get_resp = await async_client.get(f"/v1/projects/{project_id}", headers=auth_b)
    assert get_resp.status_code in (403, 404)
    assert get_resp.json()["error"]["code"] in ("FORBIDDEN", "NOT_FOUND")

    # 3. User B's list does not contain User A's project
    list_resp = await async_client.get("/v1/projects", headers=auth_b)
    assert list_resp.status_code == 200
    b_items = list_resp.json().get("items", [])
    b_ids = [p["id"] for p in b_items]
    assert project_id not in b_ids

    # 4. User B cannot delete User A's project
    del_resp = await async_client.delete(f"/v1/projects/{project_id}", headers=auth_b)
    assert del_resp.status_code in (403, 404)

    # 5. User A creates an audit record under the project
    audit_id = uuid.uuid4()
    # Resolve org_id of User A
    user_a = await _provision_user(db_session, "dev-user-a", "user-a@org-a.local")
    user_b = await _provision_user(db_session, "dev-user-b", "user-b@org-b.local")

    upload = Upload(
        id=uuid.uuid4(),
        org_id=user_a.org_id,
        user_id=user_a.id,
        object_key="test/contract.sol",
        kind="sol",
        size_bytes=100,
        sha256="0" * 64,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(upload)
    await db_session.flush()

    audit = Audit(
        id=audit_id,
        org_id=user_a.org_id,
        project_id=uuid.UUID(project_id),
        upload_id=upload.id,
        status="pending",
        stage="init",
        created_by=user_a.id,
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(audit)
    await db_session.commit()

    # User B cannot read User A's audit
    audit_get_resp = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_b)
    assert audit_get_resp.status_code in (403, 404)

    # User B cannot list User A's audit
    audits_list_resp = await async_client.get("/v1/audits", headers=auth_b)
    assert audits_list_resp.status_code == 200
    audit_items = audits_list_resp.json().get("items", [])
    audit_ids = [a["id"] for a in audit_items]
    assert str(audit_id) not in audit_ids

    # 6. Database level verification:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        # On PostgreSQL, verify RLS with app.org_id set to org B
        await db_session.execute(text(f"SET LOCAL app.org_id = '{user_b.org_id}'"))
        result = await db_session.execute(
            text(f"SELECT id FROM projects WHERE id = '{project_id}'")
        )
        assert result.first() is None, "Postgres RLS leaked org A project to org B session"

        audit_result = await db_session.execute(
            text(f"SELECT id FROM audits WHERE id = '{audit_id}'")
        )
        assert audit_result.first() is None, "Postgres RLS leaked org A audit to org B session"


@pytest.mark.asyncio
async def test_cross_tenant_every_endpoint_isolation(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
) -> None:
    """
    Exhaustive cross-tenant isolation test across every API endpoint.
    Org B cannot read, write, mutate, or trigger jobs on any Org A resource.
    """
    import asyncio
    import io
    from app.config import get_settings

    settings = get_settings()
    settings.proofs_enabled = True
    settings.invariants_enabled = True

    # 1. Setup Org A full resources
    # Create Project A
    p_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Org A Private DeFi App"},
        headers=auth_a,
    )
    assert p_resp.status_code == 201
    project_a_id = p_resp.json()["id"]

    # Upload A
    sol_code = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract VaultA {
    address public owner;
    mapping(address => uint256) public balances;

    constructor() { owner = msg.sender; }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok);
        balances[msg.sender] = 0;
    }
}
"""
    files = {"file": ("VaultA.sol", io.BytesIO(sol_code.encode()), "text/plain")}
    up_resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert up_resp.status_code == 201
    upload_a_id = up_resp.json()["upload_id"]

    # Create Audit A
    audit_resp = await async_client.post(
        f"/v1/projects/{project_a_id}/audits",
        json={"upload_id": upload_a_id},
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_a_id = audit_resp.json()["audit_id"]

    # Wait for completion
    for _ in range(40):
        get_res = await async_client.get(f"/v1/audits/{audit_a_id}", headers=auth_a)
        if get_res.json().get("status") in ("complete", "failed"):
            break
        await asyncio.sleep(0.1)

    assert get_res.json()["status"] == "complete"

    # Get File A
    files_res = await async_client.get(f"/v1/audits/{audit_a_id}/files", headers=auth_a)
    assert files_res.status_code == 200
    file_a_id = files_res.json()["items"][0]["id"]

    # Get Finding A
    findings_res = await async_client.get(f"/v1/audits/{audit_a_id}/findings", headers=auth_a)
    assert findings_res.status_code == 200
    items = findings_res.json().get("items", [])
    assert len(items) > 0
    finding_a_id = items[0]["id"]

    # Create Patch A
    patch_resp = await async_client.post(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/patches",
        headers=auth_a,
    )
    assert patch_resp.status_code == 202
    patch_a_id = patch_resp.json()["patch_id"]

    # Create API Key A
    key_resp = await async_client.post(
        "/v1/api-keys",
        json={"name": "Org A Key", "scopes": ["audits:read"]},
        headers=auth_a,
    )
    assert key_resp.status_code == 201
    api_key_a_id = key_resp.json()["id"]

    # 2. Org B attempts to access Org A's resources across EVERY endpoint:

    # Projects
    res = await async_client.get(f"/v1/projects/{project_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"GET project: expected 403/404, got {res.status_code}"

    res = await async_client.delete(f"/v1/projects/{project_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"DELETE project: expected 403/404, got {res.status_code}"

    # Audits under Project
    res = await async_client.post(
        f"/v1/projects/{project_a_id}/audits",
        json={"upload_id": upload_a_id},
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"POST project audit: expected 403/404, got {res.status_code}"

    # Audit lifecycle
    res = await async_client.get(f"/v1/audits/{audit_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"GET audit: expected 403/404, got {res.status_code}"

    res = await async_client.post(f"/v1/audits/{audit_a_id}/cancel", headers=auth_b)
    assert res.status_code in (403, 404), f"POST cancel audit: expected 403/404, got {res.status_code}"

    res = await async_client.delete(f"/v1/audits/{audit_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"DELETE audit: expected 403/404, got {res.status_code}"

    # Files
    res = await async_client.get(f"/v1/audits/{audit_a_id}/files", headers=auth_b)
    assert res.status_code in (403, 404), f"GET audit files: expected 403/404, got {res.status_code}"

    res = await async_client.get(f"/v1/audits/{audit_a_id}/files/{file_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"GET audit file: expected 403/404, got {res.status_code}"

    # Privilege map & roles
    res = await async_client.get(f"/v1/audits/{audit_a_id}/privilege-map", headers=auth_b)
    assert res.status_code in (403, 404), f"GET privilege map: expected 403/404, got {res.status_code}"

    res = await async_client.get(f"/v1/audits/{audit_a_id}/role-declarations", headers=auth_b)
    assert res.status_code in (403, 404), f"GET role-declarations: expected 403/404, got {res.status_code}"

    res = await async_client.put(
        f"/v1/audits/{audit_a_id}/role-declarations",
        json={"declarations": [{"role_key": "ADMIN", "holder_type": "multisig"}]},
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"PUT role-declarations: expected 403/404, got {res.status_code}"

    # Findings
    res = await async_client.get(f"/v1/audits/{audit_a_id}/findings", headers=auth_b)
    assert res.status_code in (403, 404), f"GET findings: expected 403/404, got {res.status_code}"

    res = await async_client.get(f"/v1/audits/{audit_a_id}/findings/{finding_a_id}", headers=auth_b)
    assert res.status_code in (403, 404), f"GET finding: expected 403/404, got {res.status_code}"

    res = await async_client.patch(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}",
        json={"status": "resolved"},
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"PATCH finding: expected 403/404, got {res.status_code}"

    # Patches
    res = await async_client.get(f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/patches", headers=auth_b)
    assert res.status_code in (403, 404), f"GET patches: expected 403/404, got {res.status_code}"

    res = await async_client.post(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/patches",
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"POST generate patch: expected 403/404, got {res.status_code}"

    res = await async_client.get(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/patches/{patch_a_id}",
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"GET patch: expected 403/404, got {res.status_code}"

    res = await async_client.post(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/patches/{patch_a_id}/verify",
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"POST verify patch: expected 403/404, got {res.status_code}"

    # Proofs (M6)
    res = await async_client.get(f"/v1/audits/{audit_a_id}/proofs", headers=auth_b)
    assert res.status_code in (403, 404), f"GET proofs: expected 403/404, got {res.status_code}"

    res = await async_client.post(
        f"/v1/audits/{audit_a_id}/findings/{finding_a_id}/proof",
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"POST proof: expected 403/404, got {res.status_code}"

    # Invariants (M7)
    res = await async_client.get(f"/v1/audits/{audit_a_id}/invariants", headers=auth_b)
    assert res.status_code in (403, 404), f"GET invariants: expected 403/404, got {res.status_code}"

    res = await async_client.post(
        f"/v1/audits/{audit_a_id}/invariant-runs",
        json={"runs": 10},
        headers=auth_b,
    )
    assert res.status_code in (403, 404), f"POST invariant-runs: expected 403/404, got {res.status_code}"

    # Exports
    res = await async_client.get(f"/v1/audits/{audit_a_id}/export?format=json", headers=auth_b)
    assert res.status_code in (403, 404), f"GET export: expected 403/404, got {res.status_code}"

    # API Keys
    keys_b_resp = await async_client.get("/v1/api-keys", headers=auth_b)
    assert keys_b_resp.status_code == 200
    b_key_ids = [k["id"] for k in keys_b_resp.json().get("items", [])]
    assert api_key_a_id not in b_key_ids

    del_key_b_resp = await async_client.delete(f"/v1/api-keys/{api_key_a_id}", headers=auth_b)
    assert del_key_b_resp.status_code in (403, 404)

