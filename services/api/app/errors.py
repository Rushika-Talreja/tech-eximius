"""
Standard error model.
All errors follow: { "error": { "code", "message", "details", "request_id" } }
Error codes defined in backend_architecture.md § 8.
"""
from __future__ import annotations

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """
    Raise this from anywhere in the app; the global handler converts it to
    the standard error body.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
        super().__init__(message)


# ─── Convenience constructors ────────────────────────────────────────────────

def not_found(resource: str, id: str | None = None) -> AppError:
    detail = f"{resource} not found"
    if id:
        detail = f"{resource} '{id}' not found"
    return AppError("NOT_FOUND", detail, 404)


def forbidden(message: str = "Forbidden") -> AppError:
    return AppError("FORBIDDEN", message, 403)


def unauthenticated(message: str = "Authentication required") -> AppError:
    return AppError("UNAUTHENTICATED", message, 401)


def validation_error(message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError("VALIDATION_ERROR", message, 422, details)


def rate_limited(retry_after: int = 60) -> AppError:
    return AppError("RATE_LIMITED", "Rate limit exceeded", 429, {"retry_after": retry_after})


def audit_not_ready(stage: str) -> AppError:
    return AppError(
        "AUDIT_NOT_READY",
        f"Audit is not yet at stage '{stage}'",
        409,
        {"current_stage": stage},
    )


def audit_purged() -> AppError:
    return AppError(
        "AUDIT_PURGED",
        "This audit was deleted per retention policy",
        410,
    )


def payload_too_large(max_mb: int) -> AppError:
    return AppError(
        "PAYLOAD_TOO_LARGE",
        f"Upload exceeds the {max_mb} MB limit",
        413,
    )


def unsupported_source(reason: str = "Only .sol and .zip files are accepted") -> AppError:
    return AppError("UNSUPPORTED_SOURCE", reason, 422)


def out_of_scope(request: str) -> AppError:
    return AppError(
        "OUT_OF_SCOPE",
        (
            f"'{request}' is outside this tool's scope. "
            "This tool performs pre-deployment source code analysis only. "
            "No on-chain monitoring, wallet tracking, or compliance analysis."
        ),
        422,
    )


def build_failed(message: str, diagnostics: list[dict[str, Any]] | None = None) -> AppError:
    return AppError(
        "BUILD_FAILED",
        message,
        422,
        {"diagnostics": diagnostics or []},
    )


def feature_not_enabled(feature: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        f"Feature '{feature}' is not yet enabled. It will be available in a future milestone.",
        422,
        {"feature": feature},
    )
