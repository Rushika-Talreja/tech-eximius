"""
Tests for Findings Endpoints:
  - GET /v1/audits/{id}/findings (filters, pagination, 409 until ready)
  - GET /v1/audits/{id}/findings/{fid} (exact spans, evidence, disclaimer)
  - PATCH /v1/audits/{id}/findings/{fid} (dismiss excludes from score, sync recompute)
  - GET /v1/audits/{id}/observations (unscored items)
  - Tenant isolation on all findings endpoints
"""
from __future__ import annotations

import io
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import _provision_user
from app.db import Audit, AuditFile, Finding, FindingEvidence, Project, Upload


@pytest.mark.asyncio
async def test_findings_audit_not_ready_returns_409(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    user_a = await _provision_user(db_session, "dev-user-a", "user-a@org-a.local")
    org_id = user_a.org_id

    proj = Project(id=uuid.uuid4(), org_id=org_id, name="P1", created_by=user_a.id)
    upload = Upload(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_a.id,
        object_key="k",
        kind="sol",
        size_bytes=10,
        sha256="abc",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    audit = Audit(
        id=uuid.uuid4(),
        org_id=org_id,
        project_id=proj.id,
        created_by=user_a.id,
        upload_id=upload.id,
        status="running",
        stage="scanning",
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add_all([proj, upload, audit])
    await db_session.commit()

    resp = await async_client.get(f"/v1/audits/{audit.id}/findings", headers=auth_a)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "AUDIT_NOT_READY"

    resp_obs = await async_client.get(f"/v1/audits/{audit.id}/observations", headers=auth_a)
    assert resp_obs.status_code == 409


@pytest.mark.asyncio
async def test_reentrancy_classic_e2e_findings(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
    db_session: AsyncSession,
) -> None:
    # 1. Create project
    proj_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Reentrancy Project"},
        headers=auth_a,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload ReentrancyClassic.sol
    reentrancy_file = Path("fixtures/contracts/reentrancy_classic/ReentrancyClassic.sol")
    assert reentrancy_file.exists()
    content = reentrancy_file.read_bytes()

    upload_resp = await async_client.post(
        "/v1/uploads",
        files={"file": ("ReentrancyClassic.sol", content, "text/plain")},
        headers=auth_a,
    )
    assert upload_resp.status_code == 201
    upload_id = upload_resp.json()["upload_id"]

    # 3. Create Audit
    audit_resp = await async_client.post(
        f"/v1/projects/{project_id}/audits",
        json={"upload_id": upload_id},
        headers=auth_a,
    )
    assert audit_resp.status_code == 202
    audit_id = audit_resp.json()["audit_id"]

    # 4. Wait for local worker to complete
    for _ in range(30):
        get_audit = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
        if get_audit.json()["status"] == "complete":
            break
        await pytest.importorskip("asyncio").sleep(0.5)

    assert get_audit.json()["status"] == "complete"
    assert get_audit.json()["scores"]["label"] == "heuristic risk indicator"
    initial_security_score = get_audit.json()["scores"]["security"]
    assert initial_security_score < 100

    # 5. List findings
    findings_resp = await async_client.get(f"/v1/audits/{audit_id}/findings", headers=auth_a)
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    items = findings_data["items"]
    assert len(items) >= 1

    # Check for reentrancy-eth finding
    reentrancy_item = next((f for f in items if "reentrancy" in f["title"].lower()), None)
    assert reentrancy_item is not None
    assert reentrancy_item["severity"] == "high"
    assert reentrancy_item["status"] == "open"
    assert reentrancy_item["scored"] is True
    fid = reentrancy_item["id"]

    # 6. GET finding detail
    detail_resp = await async_client.get(f"/v1/audits/{audit_id}/findings/{fid}", headers=auth_a)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == fid
    assert len(detail["spans"]) >= 1
    assert detail["spans"][0]["file"].endswith(".sol")
    assert len(detail["evidence"]) >= 1
    assert detail["evidence"][0]["kind"] == "static_fact"
    assert "disclaimer" in detail

    # 7. Tenant isolation check: User B cannot access User A's findings
    b_list = await async_client.get(f"/v1/audits/{audit_id}/findings", headers=auth_b)
    assert b_list.status_code in (403, 404)

    b_detail = await async_client.get(f"/v1/audits/{audit_id}/findings/{fid}", headers=auth_b)
    assert b_detail.status_code in (403, 404)

    b_patch = await async_client.patch(
        f"/v1/audits/{audit_id}/findings/{fid}",
        json={"status": "dismissed"},
        headers=auth_b,
    )
    assert b_patch.status_code in (403, 404)

    # 8. PATCH finding to dismissed -> recomputes score synchronously!
    patch_resp = await async_client.patch(
        f"/v1/audits/{audit_id}/findings/{fid}",
        json={"status": "dismissed", "reason": "acceptable risk"},
        headers=auth_a,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "dismissed"

    # Re-fetch audit to verify that score increased (finding is excluded from score)
    updated_audit = await async_client.get(f"/v1/audits/{audit_id}", headers=auth_a)
    new_security_score = updated_audit.json()["scores"]["security"]
    assert new_security_score > initial_security_score

    # Re-open finding
    reopen_resp = await async_client.patch(
        f"/v1/audits/{audit_id}/findings/{fid}",
        json={"status": "open"},
        headers=auth_a,
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "open"


@pytest.mark.asyncio
async def test_observations_endpoint(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    user_a = await _provision_user(db_session, "dev-user-a", "user-a@org-a.local")
    org_id = user_a.org_id

    proj = Project(id=uuid.uuid4(), org_id=org_id, name="ObsProj", created_by=user_a.id)
    upload = Upload(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_a.id,
        object_key="k",
        kind="sol",
        size_bytes=10,
        sha256="abc",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    audit = Audit(
        id=uuid.uuid4(),
        org_id=org_id,
        project_id=proj.id,
        created_by=user_a.id,
        upload_id=upload.id,
        status="complete",
        stage="reporting",
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add_all([proj, upload, audit])
    await db_session.flush()

    obs_finding = Finding(
        id=uuid.uuid4(),
        audit_id=audit.id,
        org_id=org_id,
        source="llm_hypothesis",
        title="Unverified Observation",
        severity="low",
        confidence=0.5,
        description="Hypothetical observation",
        scored=False,
    )
    obs_ev = FindingEvidence(
        id=uuid.uuid4(),
        finding_id=obs_finding.id,
        org_id=org_id,
        kind="static_fact",
        title="Hypothesis note",
    )
    db_session.add_all([obs_finding, obs_ev])
    await db_session.commit()

    resp = await async_client.get(f"/v1/audits/{audit.id}/observations", headers=auth_a)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Unverified Observation"
    assert items[0]["scored"] is False
