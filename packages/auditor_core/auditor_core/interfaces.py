"""
Core interfaces and stubs for evidence retrieval and finding verification.
Real implementation is owned by the evidence workstream (Milestone M4).
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator

try:
    from auditor_schemas.models import Evidence
except ImportError:
    # Standalone fallback if schemas package not installed
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
        # Disallow raw Solidity keywords or code fragments
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


# ─── Stubs ───────────────────────────────────────────────────────────────────


async def retrieve_evidence(candidate: CandidateSummary) -> RetrievalResult:
    """
    TODO(spec): Retrieve grounded precedent evidence from security corpus.
    Real implementation owned by the evidence workstream (Milestone M4).
    """
    return RetrievalResult(evidence=[], degraded=False, corpus_version=None)


def verify_draft(
    draft: FindingDraft,
    chunks: list[Chunk],
    model: ContractSemanticModel,
    manifest: SourceManifest,
) -> FindingDraft | None:
    """
    TODO(spec): Verify LLM finding draft against retrieved chunks and semantic model.
    Real implementation owned by the evidence workstream (Milestone M4).
    """
    return draft

