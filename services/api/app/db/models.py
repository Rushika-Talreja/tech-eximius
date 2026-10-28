"""
SQLAlchemy 2.0 async database models and session management.

HARD RULES:
  - All tenant tables carry org_id with RLS: USING (org_id = current_setting('app.org_id')::uuid)
  - Every query is scoped by org_id
  - set_org_id() must be called in every DB session (see middleware)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    event,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.config import get_settings

# Multi-dialect types: compatible with both PostgreSQL and SQLite
UniversalUUID = Uuid(as_uuid=True)
UniversalJSON = JSON().with_variant(JSONB, "postgresql")
UniversalArray = JSON().with_variant(ARRAY(Text), "postgresql")


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.utcnow()


# ─── Tables ──────────────────────────────────────────────────────────────────


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("organizations.id"), nullable=False)
    idp_subject: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)  # first 8 chars
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)    # HMAC-SHA256(pepper, key)
    scopes: Mapped[list[str]] = mapped_column(UniversalArray, nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_org_created", "org_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # sol | zip
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Audit(Base):
    __tablename__ = "audits"
    __table_args__ = (Index("ix_audits_org_created", "org_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("organizations.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("projects.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id"), nullable=False)
    upload_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("uploads.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False, default=dict)
    compiler_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    toolchain: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    corpus_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_manifest: Mapped[list[dict[str, Any]] | None] = mapped_column(UniversalJSON, nullable=True)
    coverage: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    scores: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditFile(Base):
    __tablename__ = "audit_files"
    __table_args__ = (Index("ix_audit_files_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)  # denormalized for RLS
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_dependency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (Index("ix_contracts_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audit_files.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # contract|library|interface|abstract
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_type: Mapped[str | None] = mapped_column(Text, nullable=True)  # erc20|erc4626|staking|lending|other
    upgradeability: Mapped[str | None] = mapped_column(Text, nullable=True)  # none|transparent|uups|beacon|diamond|unknown
    semantic: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False)


class RoleDeclaration(Base):
    __tablename__ = "role_declarations"
    __table_args__ = (Index("ix_role_declarations_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    role_key: Mapped[str] = mapped_column(Text, nullable=False)
    holder_type: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RoleNode(Base):
    __tablename__ = "role_nodes"
    __table_args__ = (Index("ix_role_nodes_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    role_key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # owner|access_control|custom|proxy_admin
    admin_role_key: Mapped[str | None] = mapped_column(Text, nullable=True)


class PrivilegedAction(Base):
    __tablename__ = "privileged_actions"
    __table_args__ = (Index("ix_privileged_actions_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    contract_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("contracts.id"), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audit_files.id"), nullable=False)
    function_signature: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    power_category: Mapped[str] = mapped_column(Text, nullable=False)
    guard_kind: Mapped[str] = mapped_column(Text, nullable=False)
    guard_roles: Mapped[list[str]] = mapped_column(UniversalArray, nullable=False, default=list)
    mitigations: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False, default=dict)
    funds_impact: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False)


class PrivilegeResult(Base):
    __tablename__ = "privilege_results"
    __table_args__ = (Index("ix_privilege_results_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    role_key: Mapped[str] = mapped_column(Text, nullable=False)
    blast_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    worst_case: Mapped[str] = mapped_column(Text, nullable=False)
    holder_assumed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    breakdown: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (Index("ix_findings_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    detector: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="security")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(UniversalUUID, ForeignKey("audit_files.id"), nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    scored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    evidence: Mapped[list[FindingEvidence]] = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan", lazy="selectin")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (Index("ix_finding_evidence_finding", "finding_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    finding_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    facts: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)

    finding: Mapped[Finding] = relationship("Finding", back_populates="evidence")


def validate_finding_has_evidence(finding: Finding, evidences: list[FindingEvidence]) -> None:
    """Service layer validation ensuring a finding has at least one evidence row."""
    if not evidences:
        raise ValueError(f"Finding '{finding.title}' must have at least one evidence row")


@event.listens_for(Session, "before_commit")
def enforce_finding_evidence_on_commit(session: Session) -> None:
    """
    Database/session-level enforcement: every Finding has >= 1 FindingEvidence row.
    Synchronously verifies that newly added or modified findings have at least one evidence row.
    Raises IntegrityError if a finding is committed without evidence.
    """
    all_objects = list(session.identity_map.values()) + list(session.new) + list(session.dirty)
    new_or_modified_findings = [
        obj for obj in set(all_objects)
        if isinstance(obj, Finding)
    ]
    if not new_or_modified_findings:
        return

    session_evidences = [
        obj for obj in set(all_objects)
        if isinstance(obj, FindingEvidence)
    ]
    evidence_finding_ids = set()
    for ev in session_evidences:
        if ev.finding_id is not None:
            evidence_finding_ids.add(ev.finding_id)
        ev_dict = ev.__dict__
        if "finding" in ev_dict and ev_dict["finding"] is not None:
            evidence_finding_ids.add(ev_dict["finding"].id)

    for f in new_or_modified_findings:
        f_dict = f.__dict__
        has_ev = (
            f.id in evidence_finding_ids
            or bool(f_dict.get("evidence"))
        )
        if not has_ev:
            raise IntegrityError(
                statement="Finding must have at least one evidence row",
                params={"finding_id": str(f.id)},
                orig=Exception(f"Constraint violation: Finding {f.id} requires at least one evidence row"),
            )


class Patch(Base):
    __tablename__ = "patches"
    __table_args__ = (Index("ix_patches_finding", "finding_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    finding_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unified_diff: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    compiles: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    finding_cleared: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_findings: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    tests_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gas_delta: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    verification_log: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Proof(Base):
    """Milestone 6 — table created now, endpoints stubbed."""
    __tablename__ = "proofs"
    __table_args__ = (Index("ix_proofs_finding", "finding_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    finding_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    test_source: Mapped[str] = mapped_column(Text, nullable=False)
    fails_on_original: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    passes_on_patched: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    run_log: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InvariantRun(Base):
    """Milestone 7 — table created now, endpoints stubbed."""
    __tablename__ = "invariant_runs"
    __table_args__ = (Index("ix_invariant_runs_audit", "audit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=_uuid)
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    contract_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("contracts.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # passed|violated|error|skipped
    counterexample: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    run_log: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_audit_id", "audit_id", "id"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(Text, nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(UniversalJSON, nullable=True)


class CorpusDocument(Base):
    __tablename__ = "corpus_documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # doc_id
    kind: Mapped[str] = mapped_column(Text, nullable=False)   # swc | postmortem
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ─── Database engine and session factory ─────────────────────────────────────

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():  # type: ignore[return]
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite"):
            from pathlib import Path
            Path("./data").mkdir(parents=True, exist_ok=True)
            _engine = create_async_engine(
                settings.database_url,
                echo=False,
                hide_parameters=True,
            )
        else:
            _engine = create_async_engine(
                settings.database_url,
                echo=False,
                hide_parameters=True,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
    return _engine


async def init_local_db() -> None:
    """Initialize SQLite database tables when running without Postgres/Docker."""
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_db_session() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency — yields a DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
