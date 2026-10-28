"""
End-to-end Deliverable Test for Milestone M1:
1. Upload vault_basic through the API
2. Run an audit
3. See the stages in the SSE stream
4. List its files and fetch file content
5. Delete the audit (immediate purge) and assert 410 AUDIT_PURGED
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"


@pytest.mark.asyncio
async def test_m1_deliverable_e2e(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    # 1. Create project
    proj_res = await async_client.post(
        "/v1/projects",
        json={"name": "M1 Deliverable Project", "description": "Vault basic test"},
        headers=auth_a,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Upload vault_basic
    vault_file = FIXTURES_DIR / "vault_basic" / "Vault.sol"
    with open(vault_file, "rb") as f:
        up_res = await async_client.post(
            "/v1/uploads",
            files={"file": ("Vault.sol", f, "text/plain")},
            headers=auth_a,
        )
    assert up_res.status_code == 201
    up_data = up_res.json()
    assert "upload_id" in up_data
    upload_id = up_data["upload_id"]

    # 3. Trigger audit
    audit_res = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    assert audit_res.status_code == 202
    audit_data = audit_res.json()
    audit_id = audit_data["audit_id"]
    events_url = audit_data["events_url"]
    assert events_url == f"/v1/audits/{audit_id}/events"

    # Wait for the pipeline to finish
    for _ in range(40):
        detail_res = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        assert detail_res.status_code == 200
        if detail_res.json().get("status") in ("complete", "failed"):
            break
        await asyncio.sleep(0.1)

    assert detail_res.json()["status"] == "complete"
    assert detail_res.json()["compiler_version"] is not None
    assert detail_res.json()["toolchain"] is not None
    assert detail_res.json()["coverage"] is not None

    # 4. Stream and verify SSE events
    sse_res = await async_client.get(events_url, headers=auth_a)
    assert sse_res.status_code == 200
    events_text = sse_res.text
    # SSE events lines contain 'event: ...' and 'data: ...'
    assert "event: stage_started" in events_text
    assert "event: stage_completed" in events_text
    assert "event: audit_completed" in events_text

    # 5. List files
    files_res = await async_client.get(f"/v1/audits/{audit_id}/files", headers=auth_a)
    assert files_res.status_code == 200
    files_data = files_res.json()
    assert len(files_data["items"]) >= 1
    file_item = files_data["items"][0]
    file_id = file_item["id"]
    assert file_item["path"].endswith(".sol")
    assert file_item["line_count"] > 0

    # 6. Fetch single file
    file_detail = await async_client.get(
        f"/v1/audits/{audit_id}/files/{file_id}",
        headers=auth_a,
    )
    assert file_detail.status_code == 200
    assert "SimpleVault" in file_detail.json()["content"]

    # 7. Delete audit (immediate purge)
    del_res = await async_client.delete(f"/v1/audits/{audit_id}", headers=auth_a)
    assert del_res.status_code == 204

    # 8. Assert subsequent access returns 410 AUDIT_PURGED
    purged_audit_res = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
    assert purged_audit_res.status_code == 410
    assert purged_audit_res.json()["error"]["code"] == "AUDIT_PURGED"

    purged_files_res = await async_client.get(f"/v1/audits/{audit_id}/files", headers=auth_a)
    assert purged_files_res.status_code == 410
    assert purged_files_res.json()["error"]["code"] == "AUDIT_PURGED"
