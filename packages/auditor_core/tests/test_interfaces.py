import pytest
from auditor_core.interfaces import (
    CandidateSummary,
    Chunk,
    ContractSemanticModel,
    FindingDraft,
    RetrievalResult,
    SourceManifest,
    retrieve_evidence,
    verify_draft,
)


@pytest.mark.asyncio
async def test_retrieve_evidence_returns_retrieval_result() -> None:
    """retrieve_evidence must return a RetrievalResult regardless of corpus state."""
    candidate = CandidateSummary(
        vuln_classes=["reentrancy"],
        structural_facts=["external_call_in_loop"],
        detector_id="slither_reentrancy",
    )
    result = await retrieve_evidence(candidate)
    assert isinstance(result, RetrievalResult)
    # Degraded (no Qdrant in test env) or real results — both are valid
    assert isinstance(result.evidence, list)
    assert isinstance(result.degraded, bool)


def test_verify_draft_grounded_when_chunk_contains_description() -> None:
    """verify_draft returns the draft when any chunk text contains the description."""
    draft = FindingDraft(
        title="Reentrancy in deposit",
        description="reentrancy withdraw",
        severity="high",
    )
    # Chunk content contains the full description text
    chunks = [Chunk(chunk_id="c1", content="reentrancy withdraw re-enters before balance update")]
    model = ContractSemanticModel(name="Vault")
    manifest = SourceManifest(files=["Vault.sol"])

    result = verify_draft(draft, chunks, model, manifest)
    assert result == draft


def test_verify_draft_ungrounded_when_no_chunk_matches() -> None:
    """verify_draft returns None when no chunk supports the description."""
    draft = FindingDraft(
        title="Flash loan attack",
        description="price oracle manipulation via flash loan",
        severity="critical",
    )
    chunks = [Chunk(chunk_id="c1", content="unrelated content about CSS layout")]
    model = ContractSemanticModel(name="Pool")
    manifest = SourceManifest(files=["Pool.sol"])

    result = verify_draft(draft, chunks, model, manifest)
    assert result is None


def test_verify_draft_no_chunks_passes_through() -> None:
    """verify_draft with no chunks returns draft unconditionally (nothing to check)."""
    draft = FindingDraft(title="Reentrancy in deposit", description="State update follows transfer")
    result = verify_draft(draft, [], ContractSemanticModel(name="Vault"), SourceManifest(files=["Vault.sol"]))
    assert result == draft


def test_candidate_summary_rejects_source_code() -> None:
    with pytest.raises(ValueError, match="must never contain source code"):
        CandidateSummary(
            vuln_classes=["reentrancy"],
            structural_facts=["contract Vault { function withdraw() external {} }"],
        )
