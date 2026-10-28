"""
API Keys endpoints.
POST /api-keys    — Bearer only (not API key)
GET  /api-keys
DELETE /api-keys/{id}

Keys: raw shown once; only HMAC-SHA256(pepper, key) stored in DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, generate_api_key, get_principal
from app.db import ApiKey, get_db_session
from app.errors import AppError, forbidden, not_found

router = APIRouter(tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["audits:write", "audits:read"]


ALLOWED_SCOPES = {"audits:write", "audits:read"}


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    if principal.auth_type != "jwt":
        raise forbidden("API key creation requires Bearer token authentication")

    invalid_scopes = set(body.scopes) - ALLOWED_SCOPES
    if invalid_scopes:
        raise AppError("VALIDATION_ERROR", f"Invalid scopes: {invalid_scopes}", 422)

    raw_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        org_id=principal.org_id,
        user_id=principal.user_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return {
        "id": str(api_key.id),
        "name": api_key.name,
        "key": raw_key,  # shown once only
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "created_at": api_key.created_at.isoformat(),
    }


@router.get("/api-keys")
async def list_api_keys(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.org_id == principal.org_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    keys = result.scalars().all()
    return {
        "items": [
            {
                "id": str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "scopes": k.scopes,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "revoked_at": None,
                "created_at": k.created_at.isoformat(),
            }
            for k in keys
        ]
    }


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    api_key = await session.get(ApiKey, key_id)
    if not api_key or api_key.org_id != principal.org_id:
        raise not_found("API key", str(key_id))
    api_key.revoked_at = datetime.utcnow()
    await session.commit()
