"""Hybrid evidence retrieval for the auditor RAG pipeline.

The retriever queries the local Qdrant collection written by
:mod:`auditor_core.rag.ingest` twice -- once with a dense
``BAAI/bge-small-en-v1.5`` vector and once with a sparse ``Qdrant/bm25``
vector -- and fuses the two rankings with Reciprocal Rank Fusion.

RRF uses ``k=60`` and a raw score of ``sum(1 / (60 + rank))``. Those raw
values are tiny (a hit ranked first in both lists scores ``2 / 61``), so the
fused scores are normalised against the best candidate of the run: the top
hit is always ``1.0`` and ``min_score`` acts as a relative cut-off.

Every FastEmbed and Qdrant call is guarded. When the store is unreachable,
the collection is missing or a model cannot be loaded, the call degrades to
an empty :class:`RetrievalResult` instead of raising.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from auditor_core.rag.ingest import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    EMBEDDING_MODEL,
    LEVEL_INCIDENT,
    SPARSE_MODEL,
    SPARSE_VECTOR_NAME,
)

logger = logging.getLogger(__name__)

__all__ = ["Evidence", "RetrievalResult", "retrieve_evidence"]

#: Repository root, derived from this file so the store path is CWD-independent.
REPO_ROOT = Path(__file__).resolve().parents[4]

#: Local on-disk Qdrant store, matching ``ingest.QDRANT_LOCAL_PATH``.
QDRANT_PATH = REPO_ROOT / "qdrant_data"

#: RRF smoothing constant.
RRF_K = 60

#: Candidates pulled from each ranking before fusion.
CANDIDATE_LIMIT = 100


@dataclass
class Evidence:
    """One retrieved corpus record, quotable verbatim by the verifier."""

    kind: str
    title: str
    doc_id: str
    chunk_id: str
    source_url: str
    exact_quote: str
    score: float
    level: str


@dataclass
class RetrievalResult:
    """Fused evidence plus the ``degraded`` soft-fail flag."""

    evidence: list[Evidence]
    degraded: bool
    corpus_version: str = "1.0.0"


def retrieve_evidence(
    query: str,
    vuln_classes: list[str] | None = None,
    swc_ids: list[str] | None = None,
    top_k: int = 20,
    min_score: float = 0.35,
) -> RetrievalResult:
    """Retrieve fused dense+sparse evidence for *query*.

    Args:
        query: Free-text search string.
        vuln_classes: Optional filter on the payload ``vuln_class`` field.
        swc_ids: Optional filter on the payload ``swc_ids`` field.
        top_k: Maximum number of evidence items returned.
        min_score: Minimum normalised RRF score (``0.0``-``1.0``).

    Returns:
        A :class:`RetrievalResult`. On any failure the evidence list is empty
        and ``degraded`` is ``True`` with ``corpus_version="unknown"``.
    """
    if top_k <= 0:
        return RetrievalResult(evidence=[], degraded=False)
    try:
        return _retrieve(query, vuln_classes, swc_ids, top_k, min_score)
    except Exception as exc:  # noqa: BLE001 - degraded mode is the contract
        logger.warning("retrieval degraded: %s", type(exc).__name__)
        return _degraded()


def _degraded() -> RetrievalResult:
    """The soft-fail result returned whenever retrieval cannot complete."""
    return RetrievalResult(evidence=[], degraded=True, corpus_version="unknown")


def _retrieve(
    query: str,
    vuln_classes: list[str] | None,
    swc_ids: list[str] | None,
    top_k: int,
    min_score: float,
) -> RetrievalResult:
    """Run the two rankings, fuse them and materialise the evidence."""
    client = QdrantClient(path=str(QDRANT_PATH))
    try:
        if not client.collection_exists(COLLECTION_NAME):
            logger.warning("collection missing: %s", COLLECTION_NAME)
            return _degraded()

        query_filter = _build_filter(vuln_classes, swc_ids)
        dense_vector, sparse_vector = _embed_query(query)

        dense_hits = client.query_points(
            collection_name=COLLECTION_NAME,
            query=dense_vector,
            using=DENSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=CANDIDATE_LIMIT,
            with_payload=True,
            with_vectors=False,
        ).points
        sparse_hits = client.query_points(
            collection_name=COLLECTION_NAME,
            query=sparse_vector,
            using=SPARSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=CANDIDATE_LIMIT,
            with_payload=True,
            with_vectors=False,
        ).points

        fused = _reciprocal_rank_fusion([dense_hits, sparse_hits])
        selected = [(point, score) for point, score in fused if score >= min_score]
        selected = selected[:top_k]

        titles = _resolve_titles(client, _doc_ids(selected))
        return RetrievalResult(
            evidence=[_to_evidence(point, score, titles) for point, score in selected],
            degraded=False,
        )
    finally:
        client.close()


def _build_filter(
    vuln_classes: list[str] | None,
    swc_ids: list[str] | None,
) -> models.Filter | None:
    """Build the payload filter, or ``None`` when no filter was requested."""
    conditions: list[models.FieldCondition] = []
    if vuln_classes:
        conditions.append(
            models.FieldCondition(
                key="vuln_class",
                match=models.MatchAny(any=list(vuln_classes)),
            )
        )
    if swc_ids:
        conditions.append(
            models.FieldCondition(
                key="swc_ids",
                match=models.MatchAny(any=list(swc_ids)),
            )
        )
    if not conditions:
        return None
    return models.Filter(must=conditions)


@lru_cache(maxsize=1)
def _dense_model() -> TextEmbedding:
    """Dense embedder, loaded once per process."""
    return TextEmbedding(model_name=EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _sparse_model() -> SparseTextEmbedding:
    """Sparse BM25 embedder, loaded once per process."""
    return SparseTextEmbedding(model_name=SPARSE_MODEL)


def _embed_query(query: str) -> tuple[list[float], models.SparseVector]:
    """Return the dense and sparse query vectors for *query*."""
    dense = next(iter(_dense_model().query_embed([query])))
    sparse = next(iter(_sparse_model().query_embed(query)))
    return (
        [float(value) for value in dense],
        models.SparseVector(
            indices=[int(index) for index in sparse.indices],
            values=[float(value) for value in sparse.values],
        ),
    )


def _reciprocal_rank_fusion(
    rankings: list[list[models.ScoredPoint]],
) -> list[tuple[models.ScoredPoint, float]]:
    """Fuse *rankings* with RRF, returning ``(point, normalised_score)`` pairs.

    The raw score of a point is ``sum(1 / (RRF_K + rank))`` over the rankings
    it appears in. Scores are then divided by the best raw score of the run,
    so the strongest candidate always scores ``1.0``.
    """
    raw: dict[models.ExtendedPointId, float] = {}
    points: dict[models.ExtendedPointId, models.ScoredPoint] = {}
    for ranking in rankings:
        for rank, point in enumerate(ranking, start=1):
            raw[point.id] = raw.get(point.id, 0.0) + 1.0 / (RRF_K + rank)
            points.setdefault(point.id, point)

    if not raw:
        return []
    best = max(raw.values())
    ordered = sorted(raw.items(), key=lambda item: item[1], reverse=True)
    return [(points[point_id], score / best) for point_id, score in ordered]


def _doc_ids(
    selected: list[tuple[models.ScoredPoint, float]],
) -> list[str]:
    """Unique, order-preserving document IDs among the selected hits."""
    doc_ids: list[str] = []
    for point, _ in selected:
        doc_id = str((point.payload or {}).get("doc_id") or "")
        if doc_id and doc_id not in doc_ids:
            doc_ids.append(doc_id)
    return doc_ids


def _resolve_titles(client: QdrantClient, doc_ids: list[str]) -> dict[str, str]:
    """Map each ``doc_id`` to its title via the parent incident record.

    The payload has no title field, so parent-child expansion reads the
    sibling ``incident`` chunk of the same document, whose text starts with
    the title line (``"{title}\\n\\n{summary}"``).
    """
    titles: dict[str, str] = {}
    if not doc_ids:
        return titles

    records, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchAny(any=doc_ids),
                ),
                models.FieldCondition(
                    key="level",
                    match=models.MatchValue(value=LEVEL_INCIDENT),
                ),
            ]
        ),
        limit=len(doc_ids),
        with_payload=True,
        with_vectors=False,
    )
    for record in records:
        payload = record.payload or {}
        doc_id = payload.get("doc_id")
        text = str(payload.get("text") or "")
        if doc_id and text:
            titles[str(doc_id)] = text.split("\n", 1)[0].strip()
    return titles


def _to_evidence(
    point: models.ScoredPoint,
    score: float,
    titles: dict[str, str],
) -> Evidence:
    """Build one :class:`Evidence` from a fused point."""
    payload = point.payload or {}
    doc_id = str(payload.get("doc_id") or "")
    title = titles.get(doc_id) or str(payload.get("incident_name") or doc_id)
    return Evidence(
        kind=str(payload.get("source_type") or ""),
        title=title,
        doc_id=doc_id,
        chunk_id=str(payload.get("chunk_id") or ""),
        source_url=str(payload.get("source_url") or ""),
        # The payload "text" is the untouched original chunk: never the
        # identifier header that was prepended for indexing.
        exact_quote=str(payload.get("text") or ""),
        score=score,
        level=str(payload.get("level") or ""),
    )
