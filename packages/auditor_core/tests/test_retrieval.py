"""Smoke tests for hybrid retrieval. Needs the SWC corpus ingested locally."""

from auditor_core.rag.retrieval import search_evidence

QUERY = "reentrancy external call before state update"


def test_unfiltered_search_not_degraded() -> None:
    result = search_evidence(QUERY)
    assert result.degraded is False
    assert len(result.evidence) > 0


def test_vuln_class_filter_reduces_results() -> None:
    unfiltered = search_evidence(QUERY)
    filtered = search_evidence(QUERY, vuln_classes=["reentrancy"])
    assert filtered.degraded is False
    assert 0 < len(filtered.evidence) < len(unfiltered.evidence)


def test_unchecked_calls_filter_returns_results() -> None:
    result = search_evidence(
        "unchecked return value of external call",
        vuln_classes=["unchecked-calls"],
    )
    assert result.degraded is False
    assert len(result.evidence) > 0