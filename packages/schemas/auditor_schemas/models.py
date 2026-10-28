"""
Core Pydantic models for DeFi Contract Auditor.

HARD RULES (from AGENTS.md):
  - Finding.evidence has min_length=1 — enforced here AND in DB service layer.
  - LLM output must be parsed into these models before persistence.
  - No free-text LLM output stored as a claim.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator


# ─── Enums ───────────────────────────────────────────────────────────────────


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Tier(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PowerCategory(StrEnum):
    SELFDESTRUCT_OR_DELEGATECALL = "SELFDESTRUCT_OR_DELEGATECALL"
    UPGRADE = "UPGRADE"
    WITHDRAW_FUNDS = "WITHDRAW_FUNDS"
    MINT = "MINT"
    CHANGE_ORACLE = "CHANGE_ORACLE"
    BURN_OTHERS = "BURN_OTHERS"
    BLACKLIST_FREEZE = "BLACKLIST_FREEZE"
    GRANT_ROLE = "GRANT_ROLE"
    CHANGE_FEE = "CHANGE_FEE"
    CHANGE_PARAMETER = "CHANGE_PARAMETER"
    PAUSE = "PAUSE"
    OTHER_PRIVILEGED = "OTHER_PRIVILEGED"


class HolderType(StrEnum):
    EOA = "eoa"
    MULTISIG = "multisig"
    TIMELOCK_MULTISIG = "timelock_multisig"
    CONTRACT_UNKNOWN = "contract_unknown"
    RENOUNCED = "renounced"


class EvidenceKind(StrEnum):
    STATIC_FACT = "static_fact"
    SWC = "swc"
    POSTMORTEM = "postmortem"
    PROOF = "proof"


class FindingSource(StrEnum):
    SLITHER = "slither"
    PRIVILEGE_MAP = "privilege_map"
    CUSTOM_DETECTOR = "custom_detector"
    INVARIANT = "invariant"
    EXPLOIT_PROOF = "exploit_proof"
    LLM_HYPOTHESIS = "llm_hypothesis"


class FindingStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    PATCHED = "patched"


class PatchStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    FAILED = "failed"
    REJECTED = "rejected"
    APPLIED = "applied"


class AuditStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditStage(StrEnum):
    BUILDING = "building"
    ANALYZING = "analyzing"
    PRIVILEGE_MAP = "privilege_map"
    SCANNING = "scanning"
    RETRIEVING = "retrieving"
    SYNTHESIZING = "synthesizing"
    PATCHING = "patching"
    VERIFYING = "verifying"
    PROVING = "proving"
    INVARIANTS = "invariants"
    REPORTING = "reporting"


class EdgeKind(StrEnum):
    CAN_CALL = "can_call"
    CAN_GRANT = "can_grant"


class ContractType(StrEnum):
    ERC20 = "erc20"
    ERC4626 = "erc4626"
    STAKING = "staking"
    LENDING = "lending"
    OTHER = "other"


class ContractKind(StrEnum):
    CONTRACT = "contract"
    LIBRARY = "library"
    INTERFACE = "interface"
    ABSTRACT = "abstract"


# ─── Core building blocks ────────────────────────────────────────────────────


class CodeSpan(BaseModel):
    """Exact source location — never omit sha256."""
    file: str
    start_line: int
    end_line: int
    sha256: str


class Evidence(BaseModel):
    """
    Evidence attached to a Finding.
    HARD GUARDRAIL: Finding.evidence must have min_length=1.
    """
    kind: EvidenceKind
    title: str
    locator: str | None = None
    source_url: HttpUrl | None = None
    chunk_id: str | None = None
    # Exact substring of stored chunk — string match, not LLM judgment
    quote: str | None = Field(default=None, max_length=500)
    retrieval_score: float | None = Field(default=None, ge=0, le=1)
    # For static_fact: raw deterministic detector output
    facts: dict[str, Any] | None = None


class Mitigations(BaseModel):
    cap: dict[str, Any] | None = None         # {value, symbol} if constant-bounded
    delay_seconds: int = 0
    two_step: bool = False
    reversible: bool = False


# ─── Privilege Map ────────────────────────────────────────────────────────────


class ScoreComponent(BaseModel):
    action_id: UUID
    base: int
    cap_mult: float
    delay_mult: float
    reversible_mult: float
    holder_mult: float
    score: int


class PrivilegedAction(BaseModel):
    id: UUID
    contract: str
    function_signature: str
    span: CodeSpan
    power_category: PowerCategory
    guard_kind: Literal["modifier", "require_sender", "role_check", "none"]
    guard_roles: list[str]
    mitigations: Mitigations
    funds_impact: int = Field(ge=0, le=3)
    score: int = Field(ge=0, le=100)
    facts: dict[str, Any]


class RoleHolderDeclaration(BaseModel):
    role_key: str
    holder_type: HolderType
    threshold: int | None = None
    signers: int | None = None
    delay_hours: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_multisig_params(self) -> "RoleHolderDeclaration":
        if self.holder_type in (HolderType.MULTISIG, HolderType.TIMELOCK_MULTISIG):
            if self.threshold is not None and self.signers is not None:
                if self.threshold > self.signers:
                    raise ValueError(
                        f"threshold ({self.threshold}) must be <= signers ({self.signers})"
                    )
        return self


class RoleRisk(BaseModel):
    role_key: str
    display_name: str
    blast_score: int = Field(ge=0, le=100)
    tier: Tier
    worst_case: str
    holder_assumed: bool
    declaration: RoleHolderDeclaration | None = None
    can_grant: list[str]
    actions: list[PrivilegedAction]
    breakdown: list[ScoreComponent]


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    kind: EdgeKind

    model_config = {"populate_by_name": True}


class PrivilegeMap(BaseModel):
    roles: list[RoleRisk]
    edges: list[Edge]
    undetected_notes: list[str]
    scoring_config_version: str = "1"
    disclaimer: str


# ─── Findings ─────────────────────────────────────────────────────────────────


class Finding(BaseModel):
    """
    HARD GUARDRAIL: evidence min_length=1 is enforced here AND in DB service.
    LLM output must be parsed through the verifier before a Finding is created.
    """
    id: UUID
    audit_id: UUID
    source: FindingSource
    detector: str | None = None
    title: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    spans: list[CodeSpan]
    description: str
    scenario: str | None = None
    # HARD GUARDRAIL — min_length=1
    evidence: list[Evidence] = Field(min_length=1)
    scored: bool = True          # False for llm_hypothesis
    patch_id: UUID | None = None
    status: FindingStatus = FindingStatus.OPEN
    created_at: datetime | None = None
    disclaimer: str = ""


class FindingSummary(BaseModel):
    id: UUID
    title: str
    severity: Severity
    confidence: float
    source: FindingSource
    status: FindingStatus
    scored: bool
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    has_patch: bool = False
    proven: bool = False


# ─── Patches ──────────────────────────────────────────────────────────────────


class PatchSummary(BaseModel):
    id: UUID
    finding_id: UUID
    status: PatchStatus


class Patch(BaseModel):
    id: UUID
    finding_id: UUID
    version: int
    status: PatchStatus
    unified_diff: str
    rationale: str
    compiles: bool | None = None
    finding_cleared: bool | None = None
    new_findings: list[dict[str, Any]] = []
    tests_passed: bool | None = None
    gas_delta: dict[str, int] = {}
    verification_log: list[dict[str, Any]] = []
    disclaimer: str = ""


# ─── Coverage ─────────────────────────────────────────────────────────────────


class CoverageStatement(BaseModel):
    """
    Honest accounting of what was and was not analyzed.
    Always included in every response — never omit.
    """
    analyzed: dict[str, Any]     # {files, contracts, detectors_run}
    not_analyzed: list[dict[str, Any]]   # [{reason, location}]
    # Fixed list — never suggest economic design, oracle trust etc. were analyzed
    out_of_scope: list[str] = Field(
        default=[
            "Economic design and tokenomics",
            "Oracle trust assumptions",
            "Governance attack economics",
            "Off-chain components and infrastructure",
            "Deployment configuration (constructor args, initial roles)",
        ]
    )


# ─── Audit Report ─────────────────────────────────────────────────────────────


class AuditReport(BaseModel):
    audit_id: UUID
    status: AuditStatus
    coverage: CoverageStatement
    privilege_map: PrivilegeMap | None = None
    findings: list[Finding]
    patches: list[PatchSummary] = []
    toolchain: dict[str, str]
    corpus_version: str | None = None
    # HARD RULE: always populated
    disclaimer: str
