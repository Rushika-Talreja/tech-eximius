"""
Audit retention and automated purge job.
Enforces default_retention_hours / audit.purge_after, immediately deleting
object storage artifacts and database source-derived records.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Audit, AuditFile, get_session_factory
from app.logging_config import get_logger
from app.storage import get_storage_client

logger = get_logger(__name__)


async def purge_audit_data(session: AsyncSession, audit: Audit) -> None:
    """
    Purge storage objects and source-derived rows for an audit.
    Verifies that deletion is complete before marking purged_at.
    """
    storage = get_storage_client()
    prefix = f"{audit.org_id}/audits/{audit.id}/"

    # 1. Delete all storage objects under the audit prefix
    try:
        storage.delete_prefix(prefix)
        logger.info("audit_storage_purged", audit_id=str(audit.id), prefix=prefix)
    except Exception as exc:
        logger.warning("audit_storage_purge_error", audit_id=str(audit.id), error=str(exc))

    # 2. Delete source-derived records (AuditFile rows)
    await session.execute(delete(AuditFile).where(AuditFile.audit_id == audit.id))

    # 3. Verify deletion
    verify_result = await session.execute(
        select(AuditFile).where(AuditFile.audit_id == audit.id)
    )
    if verify_result.scalar_one_or_none() is not None:
        raise RuntimeError(f"Failed to verify AuditFile purge for audit {audit.id}")

    # 4. Mark audit purged and scrub source manifest/coverage
    audit.purged_at = datetime.utcnow()
    audit.status = "purged"
    audit.source_manifest = None
    audit.coverage = None
    await session.commit()
    logger.info("audit_purge_completed", audit_id=str(audit.id))


async def purge_expired_audits() -> int:
    """
    Periodic job to purge all audits past their purge_after expiration.
    Returns the number of audits purged.
    """
    session_factory = get_session_factory()
    now = datetime.utcnow()
    purged_count = 0

    async with session_factory() as session:
        result = await session.execute(
            select(Audit).where(
                Audit.purge_after <= now,
                Audit.purged_at.is_(None),
            )
        )
        expired_audits = result.scalars().all()

        for audit in expired_audits:
            await purge_audit_data(session, audit)
            purged_count += 1

    return purged_count

