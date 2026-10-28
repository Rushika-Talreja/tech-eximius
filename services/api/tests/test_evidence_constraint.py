import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import _provision_user
from app.db import Audit, Finding, FindingEvidence, Project, Upload, validate_finding_has_evidence


@pytest.mark.asyncio
async def test_service_layer_evidence_validation():
    f = Finding(
        id=uuid.uuid4(),
        audit_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        source="slither",
        title="Test Finding",
        severity="high",
        confidence=0.85,
        description="desc",
    )
    # Empty evidence list must raise ValueError
    with pytest.raises(ValueError, match="must have at least one evidence row"):
        validate_finding_has_evidence(f, [])

    # Valid evidence list passes
    ev = FindingEvidence(
        id=uuid.uuid4(),
        finding_id=f.id,
        org_id=f.org_id,
        kind="static_fact",
        title="Evidence",
    )
    validate_finding_has_evidence(f, [ev])


@pytest.mark.asyncio
async def test_db_commit_without_evidence_fails(db_session: AsyncSession):
    user_a = await _provision_user(db_session, "dev-user-a", "user-a@org-a.local")
    org_id = user_a.org_id

    proj = Project(
        id=uuid.uuid4(),
        org_id=org_id,
        name="Direct DB Test Project",
        created_by=user_a.id,
    )
    upload = Upload(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_a.id,
        object_key="test/contract.sol",
        kind="sol",
        size_bytes=100,
        sha256="0" * 64,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add_all([proj, upload])
    await db_session.flush()

    audit = Audit(
        id=uuid.uuid4(),
        org_id=org_id,
        project_id=proj.id,
        upload_id=upload.id,
        status="running",
        stage="scanning",
        created_by=user_a.id,
        purge_after=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(audit)
    await db_session.flush()

    # 1. Direct insert of finding WITHOUT evidence must fail at commit
    f_orphan = Finding(
        id=uuid.uuid4(),
        audit_id=audit.id,
        org_id=org_id,
        source="slither",
        title="Orphan Finding",
        severity="high",
        confidence=0.85,
        description="no evidence",
    )
    db_session.add(f_orphan)

    with pytest.raises(IntegrityError, match="Finding must have at least one evidence row"):
        await db_session.commit()

    await db_session.rollback()

    # 2. Direct insert of finding WITH evidence must succeed
    f_valid = Finding(
        id=uuid.uuid4(),
        audit_id=audit.id,
        org_id=org_id,
        source="slither",
        title="Valid Finding",
        severity="high",
        confidence=0.85,
        description="has evidence",
    )
    ev_valid = FindingEvidence(
        id=uuid.uuid4(),
        finding_id=f_valid.id,
        org_id=org_id,
        kind="static_fact",
        title="Valid Evidence",
    )
    db_session.add(f_valid)
    db_session.add(ev_valid)
    await db_session.commit()
