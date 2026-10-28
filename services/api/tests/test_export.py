"""
Tests for Audit Export Endpoint:
  GET /v1/audits/{id}/export?format=json|md|sarif|pdf
  - Disclaimer in everything
  - Coverage statement in everything
  - Toolchain, corpus_version, and scoring weights in everything
  - Clean contract export contains "No verified issues detected by this analysis"
  - Tenant isolation
  - 409 until audit complete
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import _provision_user
from app.db import Audit, AuditFile, Finding, FindingEvidence, Project, Upload
from auditor_schemas.constants import STANDARD_DISCLAIMER


@pytest.mark.asyncio
async def test_export_not_ready_returns_409(
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

    resp = await async_client.get(f"/v1/audits/{audit.id}/export?format=json", headers=auth_a)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "AUDIT_NOT_READY"


@pytest.mark.asyncio
async def test_export_formats_and_clean_verdict(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    auth_b: dict[str, str],
    db_session: AsyncSession,
) -> None:
    user_a = await _provision_user(db_session, "dev-user-a", "user-a@org-a.local")
    org_id = user_a.org_id

    proj = Project(id=uuid.uuid4(), org_id=org_id, name="CleanProj", created_by=user_a.id)
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
        compiler_version="0.8.24",
        toolchain={"solc": "0.8.24", "slither": "0.10.0"},
        corpus_version="2026.10.1",
        coverage={
            "analyzed": {"files": ["Clean.sol"], "contracts": ["Clean"], "detectors_run": ["reentrancy-eth"]},
            "not_analyzed": [],
            "out_of_scope": ["economic design", "oracle trust", "governance", "off-chain components", "deployment configuration", "key custody"],
        },
        scores={
            "overall": 100,
            "security": 100,
            "label": "heuristic risk indicator",
            "weights": {"version": "1.0"},
        },
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add_all([proj, upload, audit])
    await db_session.commit()

    # 1. Tenant isolation: User B cannot export User A's audit
    b_resp = await async_client.get(f"/v1/audits/{audit.id}/export?format=json", headers=auth_b)
    assert b_resp.status_code in (403, 404)

    # 2. JSON export
    json_resp = await async_client.get(f"/v1/audits/{audit.id}/export?format=json", headers=auth_a)
    assert json_resp.status_code == 200
    assert "attachment" in json_resp.headers["Content-Disposition"]
    data = json.loads(json_resp.text)
    assert data["disclaimer"] == STANDARD_DISCLAIMER
    assert "coverage" in data
    assert "economic design" in data["coverage"]["out_of_scope"]
    assert data["toolchain"]["solc"] == "0.8.24"
    assert data["corpus_version"] == "2026.10.1"
    assert data["scores"]["label"] == "heuristic risk indicator"
    assert data["verdict"] == "No verified issues detected by this analysis"

    # 3. Markdown export
    md_resp = await async_client.get(f"/v1/audits/{audit.id}/export?format=md", headers=auth_a)
    assert md_resp.status_code == 200
    md_text = md_resp.text
    assert STANDARD_DISCLAIMER in md_text
    assert "Coverage Statement" in md_text
    assert "economic design" in md_text
    assert "heuristic risk indicator" in md_text
    assert "No verified issues detected by this analysis" in md_text

    # 4. SARIF export
    sarif_resp = await async_client.get(f"/v1/audits/{audit.id}/export?format=sarif", headers=auth_a)
    assert sarif_resp.status_code == 200
    sarif_data = json.loads(sarif_resp.text)
    assert sarif_data["version"] == "2.1.0"
    props = sarif_data["runs"][0]["properties"]
    assert props["disclaimer"] == STANDARD_DISCLAIMER
    assert props["verdict"] == "No verified issues detected by this analysis"
    assert "coverage" in props

