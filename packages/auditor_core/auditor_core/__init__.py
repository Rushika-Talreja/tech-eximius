"""auditor_core — Analysis, privilege map, RAG, and verification library."""
from __future__ import annotations

from auditor_core.interfaces import (
    CandidateSummary,
    Chunk,
    ContractSemanticModel,
    Evidence,
    FindingDraft,
    RetrievalResult,
    SourceManifest,
    retrieve_evidence,
    verify_draft,
)

from auditor_core.pipeline.building import (
    BuildFailedError,
    BuildingResult,
    run_building_stage,
)
from auditor_core.sandbox.runner import ExecutionResult, SandboxRunner

__version__ = "0.1.0"

__all__ = [
    "BuildFailedError",
    "BuildingResult",
    "CandidateSummary",
    "Chunk",
    "ContractSemanticModel",
    "Evidence",
    "ExecutionResult",
    "FindingDraft",
    "RetrievalResult",
    "SandboxRunner",
    "SourceManifest",
    "retrieve_evidence",
    "run_building_stage",
    "verify_draft",
]
