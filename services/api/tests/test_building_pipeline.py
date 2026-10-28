"""
Tests for Stage 1: Building.
- Compile success with vault_basic fixture: manifest, audit_files, SSE events, toolchain.
- Compile failure with compile_error (Broken.sol) fixture: status failed, BUILD_FAILED code, diagnostics.
- Mixed pragmas handling with mixed_pragmas fixture: compatible group compiled, incompatible reported in not_analyzed.
"""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Audit, AuditEvent, AuditFile


@pytest.mark.asyncio
async def test_compile_success_vault_basic(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    # 1. Create project
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Vault Project"},
        headers=auth_a,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload Vault.sol
    fixture_path = Path("fixtures/contracts/vault_basic/Vault.sol")
    assert fixture_path.exists()
    sol_bytes = fixture_path.read_bytes()

    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": ("Vault.sol", io.BytesIO(sol_bytes), "text/plain")},
        headers=auth_a,
    )
    assert upload_resp.status_code == 201
    upload_id = upload_resp.json()["upload_id"]

    # 3. Create Audit
    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={
            "upload_id": upload_id,
            "options": {"solc_version": "0.8.24", "features": ["privilege_map", "findings"]},
            "role_declarations": [],
        },
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_data = audit_resp.json()
    audit_id = audit_data["audit_id"]
    events_url = audit_data["events_url"]
    assert f"/v1/audits/{audit_id}/events" in events_url

    # 4. Wait briefly for background execution to complete
    max_wait = 15
    completed = False
    for _ in range(max_wait * 5):
        await asyncio.sleep(0.2)
        get_resp = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_resp.status_code == 200:
            status = get_resp.json()["status"]
            if status in ("complete", "failed"):
                completed = True
                break

    assert completed, "Audit did not finish within timeout"
    final_audit = get_resp.json()
    assert final_audit["status"] == "complete", f"Audit failed: {final_audit.get('error')}"
    assert final_audit["compiler_version"] == "0.8.24"
    assert "toolchain" in final_audit
    assert final_audit["toolchain"]["solc"] == "0.8.24"
    assert "disclaimer" in final_audit

    # 5. Check files list and content
    files_resp = await async_client.get(f"/v1/audits/{audit_id}/files", headers=auth_a)
    assert files_resp.status_code == 200
    files_data = files_resp.json()
    items = files_data["items"]
    assert len(items) >= 1
    vault_file = items[0]
    assert "src/Contract.sol" in vault_file["path"] or "Vault.sol" in vault_file["path"]
    assert vault_file["sha256"] != ""
    assert vault_file["line_count"] > 10

    # Fetch file content
    file_id = vault_file["id"]
    file_content_resp = await async_client.get(
        f"/v1/audits/{audit_id}/files/{file_id}",
        headers=auth_a,
    )
    assert file_content_resp.status_code == 200
    file_data = file_content_resp.json()
    assert "contract SimpleVault" in file_data["content"]

    # 6. Check AuditEvents
    import uuid
    events_query = await db_session.execute(
        select(AuditEvent).where(AuditEvent.audit_id == uuid.UUID(audit_id)).order_by(AuditEvent.id)
    )
    events = events_query.scalars().all()
    event_messages = [e.message for e in events]
    assert any("Starting stage building" in m for m in event_messages)
    assert any("Building stage complete" in m or "Completed stage building" in m for m in event_messages)


@pytest.mark.asyncio
async def test_compile_error_broken_contract(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    # 1. Create project
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Broken Project"},
        headers=auth_a,
    )
    project_id = proj_resp.json()["id"]

    # 2. Upload Broken.sol
    fixture_path = Path("fixtures/contracts/compile_error/Broken.sol")
    sol_bytes = fixture_path.read_bytes()

    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": ("Broken.sol", io.BytesIO(sol_bytes), "text/plain")},
        headers=auth_a,
    )
    upload_id = upload_resp.json()["upload_id"]

    # 3. Create Audit
    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={
            "upload_id": upload_id,
            "options": {"solc_version": "0.8.24"},
        },
        headers=auth_a,
    )
    audit_id = audit_resp.json()["audit_id"]

    # 4. Wait for background execution to complete
    completed = False
    for _ in range(40):
        await asyncio.sleep(0.2)
        get_resp = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_resp.status_code == 200:
            status = get_resp.json()["status"]
            if status in ("complete", "failed"):
                completed = True
                break

    assert completed
    audit = get_resp.json()
    assert audit["status"] == "failed"
    assert audit["error"] is not None
    assert audit["error"]["code"] == "BUILD_FAILED"
    diagnostics = audit["error"]["details"]["diagnostics"]
    assert len(diagnostics) > 0
    # Diagnostic fields check (file, line, column, message only)
    diag = diagnostics[0]
    assert "file" in diag
    assert "line" in diag
    assert "column" in diag
    assert "message" in diag


@pytest.mark.asyncio
async def test_mixed_pragmas_partitioning(
    async_client: AsyncClient,
    auth_a: dict[str, str],
) -> None:
    # Package VaultV8.sol (0.8.24) and LegacyToken.sol (0.7.6) into a zip
    buf = io.BytesIO()
    v8_bytes = Path("fixtures/contracts/mixed_pragmas/VaultV8.sol").read_bytes()
    legacy_bytes = Path("fixtures/contracts/mixed_pragmas/LegacyToken.sol").read_bytes()

    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("src/VaultV8.sol", v8_bytes)
        zf.writestr("src/LegacyToken.sol", legacy_bytes)

    buf.seek(0)
    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": ("mixed.zip", buf, "application/zip")},
        headers=auth_a,
    )
    upload_id = upload_resp.json()["upload_id"]

    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Mixed Pragmas Project"},
        headers=auth_a,
    )
    project_id = proj_resp.json()["id"]

    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id, "options": {"solc_version": "0.8.24"}},
        headers=auth_a,
    )
    audit_id = audit_resp.json()["audit_id"]

    # Wait for completion
    for _ in range(40):
        await asyncio.sleep(0.2)
        get_resp = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_resp.status_code == 200 and get_resp.json()["status"] in ("complete", "failed"):
            break

    audit = get_resp.json()
    assert audit["status"] == "complete"
    assert audit["compiler_version"] == "0.8.24"

    # Check coverage not_analyzed for the 0.7.6 file
    coverage = audit.get("coverage", {})
    not_analyzed = coverage.get("not_analyzed", [])
    assert len(not_analyzed) >= 1
    legacy_entry = next((e for e in not_analyzed if "LegacyToken.sol" in e["file"]), None)
    assert legacy_entry is not None
    assert legacy_entry["reason"] == "incompatible_pragma"

