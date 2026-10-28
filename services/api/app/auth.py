"""
Authentication and authorization.

Supports:
  1. Bearer JWT (OIDC, dashboard)  — validated via JWKS
  2. X-API-Key (CI/automation)     — HMAC-SHA256(pepper, key) lookup

HARD RULE: Every DB session must set app.org_id for RLS.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import Depends, Header, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ApiKey, Organization, User, get_db_session
from app.errors import AppError, forbidden, unauthenticated
from app.logging_config import get_logger

logger = get_logger(__name__)

JWKS_CACHE: dict[str, Any] = {}


@dataclass
class Principal:
    org_id: uuid.UUID
    user_id: uuid.UUID
    scopes: list[str]
    auth_type: str  # "jwt" | "api_key"


# ─── JWKS helpers ────────────────────────────────────────────────────────────


def _load_local_jwks() -> dict[str, Any] | None:
    """Load dev JWKS when APP_ENV=local."""
    settings = get_settings()
    if settings.is_prod or settings.app_env != "local":
        return None
    try:
        from app.devtools.mint_token import ensure_dev_keys
        _, jwks = ensure_dev_keys()
        return jwks
    except Exception as exc:
        logger.debug("no_local_jwks", error=str(exc))
        return None


async def _get_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch JWKS (cached in memory; in prod use a proper cache with TTL)."""
    settings = get_settings()
    if "keys" not in JWKS_CACHE:
        JWKS_CACHE["keys"] = []

    # In local dev, accept the local public key through local JWKS source
    if not settings.is_prod and settings.app_env == "local":
        local_jwks = _load_local_jwks()
        if local_jwks and "keys" in local_jwks:
            existing_kids = {k.get("kid") for k in JWKS_CACHE["keys"] if isinstance(k, dict)}
            for k in local_jwks["keys"]:
                if k.get("kid") not in existing_kids:
                    JWKS_CACHE["keys"].append(k)

    if not JWKS_CACHE["keys"]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(jwks_url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if "keys" in data:
                    JWKS_CACHE["keys"].extend(data["keys"])
                else:
                    JWKS_CACHE.update(data)
        except Exception as exc:
            if not JWKS_CACHE.get("keys"):
                raise unauthenticated(f"Failed to fetch JWKS: {exc}") from exc
    return JWKS_CACHE


async def _decode_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        jwks = await _get_jwks(settings.oidc_jwks_url)
        payload: dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url,
            options={"verify_exp": True},
        )
        return payload
    except JWTError as exc:
        raise unauthenticated(f"Invalid token: {exc}") from exc


# ─── API key helpers ──────────────────────────────────────────────────────────


def _hash_api_key(pepper: str, key: str) -> str:
    """HMAC-SHA256(pepper, key) — pepper stored in config, never in DB."""
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (raw_key, prefix, hash).
    raw_key shown once to user; only hash stored in DB.
    """
    raw = "ak_live_" + secrets.token_urlsafe(32)
    prefix = raw[:8]
    settings = get_settings()
    key_hash = _hash_api_key(settings.api_key_hash_pepper, raw)
    return raw, prefix, key_hash


# ─── User provisioning (first login) ─────────────────────────────────────────


async def _provision_user(
    session: AsyncSession,
    idp_subject: str,
    email: str,
) -> User:
    """Provision org + user on first OIDC login."""
    result = await session.execute(select(User).where(User.idp_subject == idp_subject))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    org = Organization(name=email.split("@")[1] if "@" in email else "My Org")
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        idp_subject=idp_subject,
        email=email,
        role="owner",
    )
    session.add(user)
    await session.flush()
    logger.info("provisioned_user", user_id=str(user.id), org_id=str(org.id))
    return user


# ─── Session RLS helper ───────────────────────────────────────────────────────


async def set_rls_org(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Set app.org_id for the current transaction — enables RLS on Postgres."""
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        await session.execute(text(f"SET LOCAL app.org_id = '{org_id}'"))


# ─── FastAPI dependencies ─────────────────────────────────────────────────────


async def get_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    session: AsyncSession = Depends(get_db_session),
) -> Principal:
    """
    Dependency that validates auth and returns Principal.
    Sets app.org_id on the DB session for RLS.
    """
    settings = get_settings()

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        payload = await _decode_jwt(token)
        sub = payload.get("sub", "")
        if not sub:
            raise unauthenticated("Token missing subject (sub)")
        email = payload.get("email", sub)

        user = await _provision_user(session, sub, email)
        await set_rls_org(session, user.org_id)
        return Principal(
            org_id=user.org_id,
            user_id=user.id,
            scopes=["audits:write", "audits:read"],
            auth_type="jwt",
        )

    if x_api_key:
        key_hash = _hash_api_key(settings.api_key_hash_pepper, x_api_key)
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise unauthenticated("Invalid API key")
        if api_key.revoked_at is not None:
            raise unauthenticated("API key is revoked")

        from datetime import datetime
        api_key.last_used_at = datetime.utcnow()
        await session.commit()
        await set_rls_org(session, api_key.org_id)
        return Principal(
            org_id=api_key.org_id,
            user_id=api_key.user_id,
            scopes=list(api_key.scopes),
            auth_type="api_key",
        )

    raise unauthenticated()


def require_scope(scope: str):
    """Factory for scope-checking dependencies."""
    async def _check(principal: Principal = Depends(get_principal)) -> Principal:
        if scope not in principal.scopes:
            raise forbidden(f"Scope '{scope}' is required")
        return principal
    return Depends(_check)


# Convenience aliases
RequireRead = Depends(get_principal)
RequireWrite = require_scope("audits:write")
