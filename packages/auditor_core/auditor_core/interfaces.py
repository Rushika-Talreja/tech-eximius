"""
Core interfaces for evidence retrieval and finding verification (Milestone M4).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

try:
    from auditor_schemas.models import Evidence
except ImportError:
    from pydantic import HttpUrl

    class Evidence(BaseModel):  # type: ignore[no-redef]
        kind: str
        title: str
        locator: str | None = None
        source_url: HttpUrl | None = None
        chunk_id: str | None = None
        quote: str | None = None
        retrieval_score: float | None = None
        facts: dict[str, Any] | None = None


class CandidateSummary(BaseModel):
    """
    Candidate vulnerability summary used for evidence retrieval.
    HARD RULE: Must never contain customer source code.
    """
    vuln_classes: list[str] = Field(default_factory=list)
    structural_facts: list[str] = Field(default_factory=list)
    detector_id: str | None = None

    @field_validator("vuln_classes", "structural_facts")
    @classmethod
    def reject_source_code(cls, values: list[str]) -> list[str]:
        code_markers = ["pragma solidity", "contract ", "function ", "assembly {", "mapping("]
        for val in values:
            for marker in code_markers:
                if marker in val:
                    raise ValueError(f"CandidateSummary must never contain source code (detected '{marker}')")
        return values


class RetrievalResult(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    degraded: bool = False
    corpus_version: str | None = None


class Chunk(BaseModel):
    chunk_id: str
    content: str = ""
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FindingDraft(BaseModel):
    title: str
    category: str = "security"
    description: str = ""
    detector: str | None = None
    severity: str = "medium"


from auditor_core.privilege_map.semantic import ContractSemanticModel


class SourceManifest(BaseModel):
    files: list[str] = Field(default_factory=list)
    sha256: str = ""


# ─── M4 real implementations ─────────────────────────────────────────────────


async def retrieve_evidence(candidate: CandidateSummary) -> RetrievalResult:
    """Retrieve grounded precedent evidence from the security corpus via RAG."""
    from auditor_core.rag.retrieval import retrieve_evidence as _retrieve

    return await _retrieve(candidate)  # type: ignore[return-value]


def verify_draft(
    draft: FindingDraft,
    chunks: list[Chunk],
    model: ContractSemanticModel,
    manifest: SourceManifest,
) -> FindingDraft | None:
    """Verify a finding draft against retrieved chunks.

    Uses the description as the candidate quote for a relaxed substring match.
    Returns the draft when grounded, None when no chunk supports the claim.
    When no chunks are provided the draft is returned unconditionally (nothing
    to check against).
    """
    if not chunks:
        return draft

    from auditor_core.rag.retrieval import Evidence as RagEvidence
    from auditor_core.verifier.verify import Claim
    from auditor_core.verifier.verify import verify_draft as _verify

    evidence = [
        RagEvidence(
            kind="chunk",
            title=chunk.chunk_id,
            doc_id=chunk.chunk_id,
            chunk_id=chunk.chunk_id,
            source_url=chunk.source_url or "",
            exact_quote=chunk.content,
            score=1.0,
            level="chunk",
        )
        for chunk in chunks
    ]

    # Use the draft description as the quote to match against chunk content.
    # Relaxed check (case-insensitive, whitespace-normalised) so that partial
    # description fragments still ground the claim.
    claim = Claim(
        claim_id=draft.title,
        title=draft.title,
        description=draft.description,
        swc_id=None,
        severity=draft.severity,
        quoted_evidence=draft.description or None,
    )
    result = _verify([claim], evidence, strict_quote_check=False)
    return draft if result.verified_findings else None
