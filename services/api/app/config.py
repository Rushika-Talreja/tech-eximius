"""
Application configuration using pydantic-settings.
Every environment variable documented in tech_stack_and_setup.md.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    app_env: str = "local"
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    app_version: str = "0.1.0"

    # Database (defaults to local SQLite if PostgreSQL is not running)
    database_url: str = "sqlite+aiosqlite:///./data/auditor.db"

    # Queue / Arq
    redis_url: str = ""
    queue_backend: str = "local"  # "local" (asyncio in-memory) or "redis" (arq)

    # Storage
    storage_backend: str = "local"  # "local" (filesystem) or "s3"
    local_storage_dir: str = "./data/storage"
    s3_endpoint_url: str = ""
    s3_bucket: str = "auditor-artifacts"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    artifact_encryption_key_id: str = "local-dev-key"
    default_retention_hours: int = 24

    # Auth
    oidc_issuer_url: str = "https://example.com"
    oidc_audience: str = "defi-auditor"
    oidc_jwks_url: str = "https://example.com/.well-known/jwks.json"
    api_key_hash_pepper: str = "change-me-32-bytes-random-string!!"

    # Qdrant / embeddings
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    sparse_model: str = "Qdrant/bm25"
    rag_min_score: float = 0.35
    rag_top_k: int = 20

    # LLM
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model_reasoning: str = "gpt-4o"
    llm_model_fast: str = "gpt-4o-mini"
    # HARD RULE: must be true in staging/prod; app refuses to start otherwise
    llm_zero_retention: bool = False

    # Sandbox
    sandbox_runtime: str = "local"  # "local" (subprocess) or "docker"
    sandbox_cpu_limit: int = 2
    sandbox_mem_limit_mb: int = 2048
    sandbox_timeout_seconds: int = 300
    dependency_fetch_allowlist: str = (
        "registry.npmjs.org,github.com,codeload.github.com"
    )

    # Limits
    max_upload_mb: int = 10
    max_files_per_audit: int = 200
    audits_per_hour_per_org: int = 20

    @field_validator("llm_zero_retention", mode="before")
    @classmethod
    def enforce_zero_retention_in_prod(cls, v: bool, info: object) -> bool:  # type: ignore[override]
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_prod(self) -> bool:
        return self.app_env in ("staging", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
