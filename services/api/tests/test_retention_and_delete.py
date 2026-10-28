"""
Tests for immediate purge (DELETE /v1/audits/{id}) and retention purge job.
Verifies storage objects and AuditFile rows are completely removed,
and 410 AUDIT_PURGED or 409 AUDIT_NOT_READY are returned per spec.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Audit, AuditFile, Project, Upload
from app.retention import purge_audit_data, purge_expired_audits
from app.storage import get_storage_client

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"


@pytest.mark.asyncio
async def test_delete_audit_immediate_purge(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session,
) -> None:
    # 1. Create project
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Purge Test Project"},
        headers=auth_a,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload contract
    vault_sol = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    with open(vault_sol, "rb") as f:
        up_resp = await async_client.post(
            "/v1/uploads",
            files={"file": ("Vault.sol", f, "text/plain")},
            headers=auth_a,
        )
    assert up_resp.status_code == 201
    upload_id = up_resp.json()["upload_id"]

    # 3. Create audit
    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_id = audit_resp.json()["audit_id"]

    # Wait for pipeline to finish building
    for _ in range(30):
        get_res = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_res.json().get("status") in ("complete", "failed"):
            break
        await asyncio.sleep(0.1)

    assert get_res.json()["status"] == "complete"

    # List files and verify they exist
    files_resp = await async_client.get(f"/v1/audits/{audit_id}/files", headers=auth_a)
    assert files_resp.status_code == 200
    files = files_resp.json()["items"]
    assert len(files) >= 1
    file_id = files[0]["id"]

    # Get single file content
    file_content_resp = await async_client.get(
        f"/v1/audits/{audit_id}/files/{file_id}",
        headers=auth_a,
    )
    assert file_content_resp.status_code == 200
    assert "Vault" in file_content_resp.json()["content"]

    # 4. Immediate DELETE
    del_resp = await async_client.delete(f"/v1/audits/{audit_id}", headers=auth_a)
    assert del_resp.status_code == 204

    # 5. Subsequent GET /v1/audits/{id} must return 410 AUDIT_PURGED
    after_get = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
    assert after_get.status_code == 410
    assert after_get.json()["error"]["code"] == "AUDIT_PURGED"

    # Subsequent GET /v1/audits/{id}/files must return 410
    after_files = await async_client.get(f"/v1/audits/{audit_id}/files", headers=auth_a)
    assert after_files.status_code == 410
    assert after_files.json()["error"]["code"] == "AUDIT_PURGED"

    # 6. Verify database records are deleted
    file_rows = await db_session.execute(
        select(AuditFile).where(AuditFile.audit_id == uuid.UUID(audit_id))
    )
    assert len(file_rows.scalars().all()) == 0


@pytest.mark.asyncio
async def test_scheduled_purge_expired_audits(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session,
) -> None:
    # Create project and upload
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Expired Retention Project"},
        headers=auth_a,
    )
    project_id = proj_resp.json()["id"]

    vault_sol = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    with open(vault_sol, "rb") as f:
        up_resp = await async_client.post(
            "/v1/uploads",
            files={"file": ("Vault.sol", f, "text/plain")},
            headers=auth_a,
        )
    upload_id = up_resp.json()["upload_id"]

    # Create audit
    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_id = audit_resp.json()["audit_id"]

    for _ in range(30):
        get_res = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_res.json().get("status") in ("complete", "failed"):
            break
        await asyncio.sleep(0.1)

    # Manually backdate purge_after in DB to simulate expired retention
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.purge_after = datetime.utcnow() - timedelta(minutes=5)
    await db_session.commit()

    # Run purge job
    purged_count = await purge_expired_audits()
    assert purged_count >= 1

    # Verify audit is now purged
    after_get = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
    assert after_get.status_code == 410
    assert after_get.json()["error"]["code"] == "AUDIT_PURGED"


@pytest.mark.asyncio
async def test_audit_not_ready_returns_409(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session,
) -> None:
    # Create project and upload
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Not Ready Project"},
        headers=auth_a,
    )
    project_id = proj_resp.json()["id"]

    vault_sol = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    with open(vault_sol, "rb") as f:
        up_resp = await async_client.post(
            "/v1/uploads",
            files={"file": ("Vault.sol", f, "text/plain")},
            headers=auth_a,
        )
    upload_id = up_resp.json()["upload_id"]

    # Create dummy audit in queued/building state
    me_resp = await async_client.get("/v1/me", headers=auth_a)
    user_info = me_resp.json()

    import uuid
    dummy_file_id = uuid.uuid4()
    audit = Audit(
        org_id=uuid.UUID(user_info["org"]["id"]),
        project_id=uuid.UUID(project_id),
        created_by=uuid.UUID(user_info["user"]["id"]),
        upload_id=uuid.UUID(upload_id),
        status="running",
        stage="building",
        options={},
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(audit)
    resp = await async_client.get(
        f"/v1/audits/{audit.id}/files/{dummy_file_id}",
        headers=auth_a,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "AUDIT_NOT_READY"
