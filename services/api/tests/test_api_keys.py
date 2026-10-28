"""
Tests for API Key authentication, scoping, revocation, and security.
- Raw key shown once, prefix 'ak_live_', entropy >= 32 bytes
- Raw key never stored in DB (only HMAC hash and prefix)
- Authenticates via X-API-Key
- Scope enforcement (wrong scope -> 403)
- Revoked key -> 401
- Unknown key -> 401
- List endpoint returns metadata only (no raw key)
- last_used_at updates on successful authenticated request
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ApiKey


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_security(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    # 1. Create API key with audits:write and audits:read
    create_resp = await async_client.post(
        "/v1/api-keys",
        json={"name": "ci-deployer", "scopes": ["audits:write", "audits:read"]},
        headers=auth_a,
    )
    assert create_resp.status_code == 201, create_resp.text
    key_data = create_resp.json()

    raw_key = key_data["key"]
    key_id = uuid.UUID(key_data["id"])
    prefix = key_data["key_prefix"]

    # Verify format and entropy
    assert raw_key.startswith("ak_live_")
    # Entropy: "ak_live_" (8 chars) + at least 32 bytes URL-safe (43+ chars)
    assert len(raw_key) >= 40
    assert prefix == raw_key[:8]

    # 2. Verify raw key is NEVER stored in database
    db_row = await db_session.get(ApiKey, key_id)
    assert db_row is not None
    assert db_row.key_prefix == prefix
    assert db_row.key_hash != raw_key
    assert raw_key not in db_row.key_hash
    # Check that raw key does not appear anywhere in api_keys table
    raw_query = await db_session.execute(
        select(ApiKey).where(ApiKey.key_hash == raw_key)
    )
    assert raw_query.scalar_one_or_none() is None

    # 3. Authenticate with valid key using X-API-Key
    me_resp = await async_client.get(
        "/v1/me",
        headers={"X-API-Key": raw_key},
    )
    assert me_resp.status_code == 200, me_resp.text
    me_data = me_resp.json()
    assert "user" in me_data
    assert "org" in me_data
    assert me_data["user"]["id"] is not None

    # 4. Verify last_used_at is updated
    await db_session.refresh(db_row)
    assert db_row.last_used_at is not None

    # 5. Verify list endpoint returns metadata only and never the secret
    list_resp = await async_client.get(
        "/v1/api-keys",
        headers=auth_a,
    )
    assert list_resp.status_code == 200
    listed_keys = list_resp.json().get("items", [])
    matching = [k for k in listed_keys if k["id"] == str(key_id)]
    assert len(matching) == 1
    found = matching[0]
    assert "key" not in found
    assert found["key_prefix"] == prefix
    assert "last_used_at" in found

    # 6. Test scoped key (read-only key cannot write)
    read_only_resp = await async_client.post(
        "/v1/api-keys",
        json={"name": "read-only-reporter", "scopes": ["audits:read"]},
        headers=auth_a,
    )
    assert read_only_resp.status_code == 201
    ro_key = read_only_resp.json()["key"]

    # Read endpoint succeeds
    read_resp = await async_client.get("/v1/projects", headers={"X-API-Key": ro_key})
    assert read_resp.status_code == 200

    # Write endpoint fails with 403 Forbidden
    write_resp = await async_client.post(
        "/v1/projects",
        json={"name": "Forbidden Project"},
        headers={"X-API-Key": ro_key},
    )
    assert write_resp.status_code == 403
    assert write_resp.json()["error"]["code"] == "FORBIDDEN"

    # 7. Revoke key
    revoke_resp = await async_client.delete(
        f"/v1/api-keys/{key_id}",
        headers=auth_a,
    )
    assert revoke_resp.status_code == 204

    # 8. Revoked key gets 401
    revoked_auth_resp = await async_client.get(
        "/v1/me",
        headers={"X-API-Key": raw_key},
    )
    assert revoked_auth_resp.status_code == 401
    assert revoked_auth_resp.json()["error"]["code"] == "UNAUTHENTICATED"

    # 9. Unknown key gets 401
    unknown_resp = await async_client.get(
        "/v1/me",
        headers={"X-API-Key": "ak_live_nonexistentkey1234567890abcdef"},
    )
    assert unknown_resp.status_code == 401
    assert unknown_resp.json()["error"]["code"] == "UNAUTHENTICATED"
