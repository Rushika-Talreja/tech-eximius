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
