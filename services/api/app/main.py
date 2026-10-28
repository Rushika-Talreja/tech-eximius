"""
FastAPI application — DeFi Contract Auditor API.

Conventions from api_endpoints.md:
  - Base: /v1
  - All IDs: UUIDs
  - All timestamps: ISO 8601 UTC
  - Disclaimer in every audit/report/finding response
  - X-Request-Id header always echoed
  - Standard error body: { "error": { code, message, details, request_id } }
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.errors import AppError, ErrorDetail, ErrorResponse
from app.logging_config import configure_logging, get_logger
from app.routers import (
    api_keys,
    audits,
    corpus,
    exports,
    findings,
    health,
    invariants,
    patches,
    privilege_map,
    projects,
    proofs,
    uploads,
    users,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    settings = get_settings()
    configure_logging(settings.app_env)

    # HARD RULE: LLM zero-retention must be true in staging/prod
    if settings.is_prod and not settings.llm_zero_retention:
        raise RuntimeError(
            "LLM_ZERO_RETENTION must be true in staging/prod. "
            "Ensure your LLM provider contract states no retention and no training."
        )

    # Initialize local SQLite DB tables if running without external Postgres/Docker
    from app.db.models import init_local_db
    await init_local_db()

    logger.info(
        "api_startup",
        env=settings.app_env,
        version=settings.app_version,
    )
    yield
    logger.info("api_shutdown")


settings = get_settings()

app = FastAPI(
    title="DeFi Contract Auditor API",
    description=(
        "Pre-deployment smart contract analysis tool. "
        "This tool performs automated advisory analysis only — "
        "it does not constitute a formal audit or security certification."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── CORS (locked to web origin) ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


# ─── Request-ID middleware ────────────────────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    import structlog
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# ─── Global error handlers ────────────────────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    import structlog
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "unknown")
    logger.warning("app_error", code=exc.code, status=exc.status, message=exc.message)
    headers: dict[str, str] = {"X-Request-Id": request_id}
    if exc.status == 429:
        retry_after = str(exc.details.get("retry_after", 60))
        headers["Retry-After"] = retry_after
        headers["X-RateLimit-Limit"] = str(exc.details.get("limit", 60))
        headers["X-RateLimit-Remaining"] = "0"
    return JSONResponse(
        status_code=exc.status,
        content=ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            )
        ).model_dump(),
        headers=headers,
    )


@app.exception_handler(ValidationError)
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: ValidationError | RequestValidationError) -> JSONResponse:
    import structlog
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "unknown")
    errors: list[Any] = []
    for err in exc.errors():
        # Strip raw 'input' field to ensure request body / customer code is never echoed
        safe_err = {
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type"),
        }
        errors.append(safe_err)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": errors},
                request_id=request_id,
            )
        ).model_dump(),
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    import structlog
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "unknown")
    logger.exception("unhandled_error", exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL",
                message="An internal error occurred",
                request_id=request_id,
            )
        ).model_dump(),
        headers={"X-Request-Id": request_id},
    )


# ─── Routers ─────────────────────────────────────────────────────────────────
API_PREFIX = "/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(api_keys.router, prefix=API_PREFIX)
app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(uploads.router, prefix=API_PREFIX)
app.include_router(audits.router, prefix=API_PREFIX)
app.include_router(privilege_map.router, prefix=API_PREFIX)
app.include_router(findings.router, prefix=API_PREFIX)
app.include_router(patches.router, prefix=API_PREFIX)
app.include_router(proofs.router, prefix=API_PREFIX)
app.include_router(invariants.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(corpus.router, prefix=API_PREFIX)

from app.rate_limiter import rate_limit

@app.get("/v1/test-rate-limit", dependencies=[Depends(rate_limit(limit=1, window_seconds=60))])
async def test_rate_limit_endpoint() -> dict[str, str]:
    return {"status": "ok"}

if settings.app_env == "local":
    from typing import Literal

    @app.get("/v1/devtools/token", tags=["devtools"])
    async def get_dev_token(user: Literal["a", "b"] = "a") -> dict[str, str]:
        from app.devtools.mint_token import mint_token
        return {"token": mint_token(user)}

