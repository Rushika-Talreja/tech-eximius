"""
POST /uploads — multipart/form-data with zip/sol safety checks.

HARD RULES:
  - No customer code in logs (log hash/size/id only)
  - Zip safety: reject traversal, symlinks, file-count, size, bomb ratio
  - Accept only .sol and .zip
"""
from __future__ import annotations

import hashlib
import io
import os
import zipfile
from datetime import datetime, timedelta

from app.storage import get_storage_client
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.config import get_settings
from app.db import Upload, get_db_session
from app.errors import payload_too_large, unsupported_source, AppError
from app.logging_config import get_logger

router = APIRouter(tags=["uploads"])
logger = get_logger(__name__)

# TODO(spec): ratio threshold not given in doc — using 100:1 as safe default
_ZIP_MAX_RATIO = 100
_ZIP_MAX_FILE_SIZE_MB = 50  # per individual file in zip


def _validate_zip(data: bytes, max_files: int) -> None:
    """
    Zip safety checks per security_and_guardrails.md.
    Raises AppError on any violation.
    """
    compressed_size = len(data)

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()

            if len(infos) > max_files:
                raise AppError(
                    "VALIDATION_ERROR",
                    f"Zip contains {len(infos)} files; maximum is {max_files}",
                    422,
                )

            total_uncompressed = 0
            for info in infos:
                name = info.filename

                # Reject path traversal
                if ".." in name or name.startswith("/") or os.path.isabs(name):
                    raise AppError(
                        "VALIDATION_ERROR",
                        f"Zip contains path traversal entry: {name!r}",
                        422,
                    )

                # Reject symlinks
                if info.external_attr >> 16 & 0xA000 == 0xA000:
                    raise AppError(
                        "VALIDATION_ERROR",
                        f"Zip contains a symbolic link: {name!r}",
                        422,
                    )

                # Reject oversized individual files
                if info.file_size > _ZIP_MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise AppError(
                        "VALIDATION_ERROR",
                        f"File {name!r} exceeds per-file size limit",
                        422,
                    )

                total_uncompressed += info.file_size

            # Zip bomb check
            if compressed_size > 0 and total_uncompressed / compressed_size > _ZIP_MAX_RATIO:
                raise AppError(
                    "VALIDATION_ERROR",
                    "Zip compression ratio exceeds limit (possible zip bomb)",
                    422,
                )
    except zipfile.BadZipFile as exc:
        raise AppError("VALIDATION_ERROR", f"Invalid zip file: {exc}", 422) from exc


@router.post("/uploads", status_code=201)
async def create_upload(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # Validate file extension
    filename = file.filename or ""
    if not (filename.endswith(".sol") or filename.endswith(".zip")):
        raise unsupported_source("Only .sol and .zip files are accepted")

    kind = "zip" if filename.endswith(".zip") else "sol"

    # Read and validate size
    data = await file.read()
    if len(data) > max_bytes:
        raise payload_too_large(settings.max_upload_mb)

    # Zip-specific safety checks
    if kind == "zip":
        _validate_zip(data, settings.max_files_per_audit)

    # Compute hash
    sha256 = hashlib.sha256(data).hexdigest()

    # Store in MinIO — path: {org_id}/uploads/{sha256}
    import uuid
    upload_id = uuid.uuid4()
    object_key = f"{principal.org_id}/uploads/{upload_id}"

    try:
        storage = get_storage_client()
        storage.put_object(
            key=object_key,
            data=data,
            content_type="application/zip" if kind == "zip" else "text/plain",
            metadata={"sha256": sha256, "org_id": str(principal.org_id)},
        )
    except Exception as exc:
        logger.error("storage_upload_failed", upload_id=str(upload_id), error_type=type(exc).__name__)
        raise AppError("INTERNAL", "Storage upload failed", 500) from exc

    expires_at = datetime.utcnow() + timedelta(hours=settings.default_retention_hours)
    upload = Upload(
        id=upload_id,
        org_id=principal.org_id,
        user_id=principal.user_id,
        object_key=object_key,
        kind=kind,
        size_bytes=len(data),
        sha256=sha256,
        expires_at=expires_at,
    )
    session.add(upload)
    await session.commit()

    # Log IDs and hashes only — no source content
    logger.info(
        "upload_created",
        upload_id=str(upload_id),
        kind=kind,
        size_bytes=len(data),
        sha256=sha256[:16] + "...",
    )

    return {
        "upload_id": str(upload_id),
        "kind": kind,
        "size_bytes": len(data),
        "sha256": sha256,
        "expires_at": expires_at.isoformat(),
    }
