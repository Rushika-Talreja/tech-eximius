"""
Pytest configuration and fixtures for services/api.
Supports both in-memory/local SQLite and PostgreSQL via DATABASE_URL.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Base, get_engine, get_session_factory, init_local_db
from app.devtools.mint_token import mint_token
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncGenerator[None, None]:
    """Ensure database schema is created for test session."""
    settings = get_settings()
    engine = get_engine()
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # No teardown needed for ephemeral dev db


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def token_a() -> str:
    return mint_token("a")


@pytest.fixture
def token_b() -> str:
    return mint_token("b")


@pytest.fixture
def auth_a(token_a: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_a}"}


@pytest.fixture
def auth_b(token_b: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_b}"}


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session

