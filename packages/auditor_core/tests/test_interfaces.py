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
async def test_retrieve_evidence_stub() -> None:
    candidate = CandidateSummary(
        vuln_classes=["reentrancy"],
        structural_facts=["external_call_in_loop"],
        detector_id="slither_reentrancy",
    )
    result = await retrieve_evidence(candidate)
    assert isinstance(result, RetrievalResult)
    assert result.evidence == []
    assert result.degraded is False
    assert result.corpus_version is None


def test_verify_draft_stub() -> None:
    draft = FindingDraft(title="Reentrancy in deposit", description="State update follows transfer")
    chunks = [Chunk(chunk_id="chunk_1", content="precedent SWC-107")]
    model = ContractSemanticModel(name="Vault")
    manifest = SourceManifest(files=["Vault.sol"])

    verified = verify_draft(draft, chunks, model, manifest)
    assert verified == draft


def test_candidate_summary_rejects_source_code() -> None:
    with pytest.raises(ValueError, match="must never contain source code"):
        CandidateSummary(
            vuln_classes=["reentrancy"],
            structural_facts=["contract Vault { function withdraw() external {} }"],
        )

