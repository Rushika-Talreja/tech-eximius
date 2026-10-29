"""Retrieval evaluation harness for the auditor golden set.

Every query in ``golden_set.yaml`` is run through
:func:`auditor_core.rag.retrieval.retrieve_evidence` and scored with
Recall@5, Precision@5 and the negative empty-rate. Two thresholds are
swept so the retriever can be calibrated:

* ``MIN_SCORE`` -- relative RRF cut-off. It trims the tail of a result set.
* ``MIN_SIMILARITY`` -- absolute dense-cosine floor. It decides whether a
  query has an answer at all. RRF is rank-based, so ``MIN_SCORE`` alone can
  never reject a negative query; this floor is what makes the negative
  empty-rate move.

Embedding is the expensive part of a retrieval and every threshold is
applied after fusion, so each query is retrieved exactly once with the
thresholds wide open and the sweeps are evaluated from the cached evidence.

Usage::

    .\\venv\\Scripts\\python.exe eval\\retrieval\\run_eval.py
    .\\venv\\Scripts\\python.exe eval\\retrieval\\run_eval.py --verbose
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from auditor_core.rag.retrieval import Evidence, RetrievalResult, retrieve_evidence

#: Default location of the ground-truth pairs.
GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.yaml"

#: Cut-off used for the reported metrics.
TOP_K = 5

#: Recall@5 at or below this value counts as a failure.
RECALL_TARGET = 0.85

#: Threshold used as the baseline in each sweep.
DEFAULT_MIN_SCORE = 0.35

#: Candidates cached per query, wide enough for every sweep combination.
CACHE_TOP_K = 50

#: Values swept for the relative RRF cut-off.
MIN_SCORE_GRID: tuple[float, ...] = (0.10, 0.20, 0.30, 0.40, 0.50)

#: Values swept for the absolute dense-cosine floor.
MIN_SIMILARITY_GRID: tuple[float, ...] = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75)


@dataclass(frozen=True)
class GoldenQuery:
    """One ground-truth pair from ``golden_set.yaml``."""

    query_id: str
    text: str
    targets: tuple[str, ...]

    @property
    def is_negative(self) -> bool:
        """True when no corpus document answers this query."""
        return not self.targets


@dataclass(frozen=True)
class Metrics:
    """Aggregate scores for one threshold configuration."""

    recall_at_k: float
    precision_at_k: float
    negative_empty_rate: float
    positives_hit: int
    positives_total: int
    negatives_empty: int
    negatives_total: int

    @property
    def recall_ok(self) -> bool:
        """Whether Recall@k clears :data:`RECALL_TARGET`."""
        return self.recall_at_k >= RECALL_TARGET


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenQuery]:
    """Read the ground-truth pairs from *path*.

    A missing or empty ``targets`` value marks a negative case.

    Raises:
        FileNotFoundError: If *path* does not exist.
        KeyError: If an entry lacks its ``id`` or ``query`` field.
    """
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    golden_queries: list[GoldenQuery] = []
    for entry in raw.get("queries") or []:
        targets = entry.get("targets") or []
        golden_queries.append(
            GoldenQuery(
                query_id=str(entry["id"]),
                text=str(entry["query"]),
                targets=tuple(str(target) for target in targets),
            )
        )
    return golden_queries


def retrieve_all(
    golden_queries: Sequence[GoldenQuery],
    *,
    min_score: float = 0.0,
    min_similarity: float | None = None,
) -> dict[str, RetrievalResult]:
    """Retrieve every query once, keyed by query id.

    The thresholds default to "wide open" so a single embedding pass serves
    the whole sweep; :func:`_apply_thresholds` reproduces the retriever's
    own cut-offs offline.
    """
    return {
        golden.query_id: retrieve_evidence(
            golden.text,
            top_k=CACHE_TOP_K,
            min_score=min_score,
            min_similarity=min_similarity,
        )
        for golden in golden_queries
    }


def evaluate(
    golden_queries: Sequence[GoldenQuery],
    cache: dict[str, RetrievalResult],
    *,
    min_score: float,
    min_similarity: float | None,
) -> Metrics:
    """Score *golden_queries* under one threshold configuration.

    Recall@5 counts a positive query as a hit when at least one target
    ``doc_id`` appears in the top 5. Precision@5 is the mean share of the
    distinct documents in the top 5 that are targets. The negative
    empty-rate is the share of negative queries that come back with no
    evidence at all.
    """
    positives_hit = 0
    positives_total = 0
    negatives_empty = 0
    negatives_total = 0
    precisions: list[float] = []

    for golden in golden_queries:
        evidence = _apply_thresholds(
            cache[golden.query_id].evidence, min_score, min_similarity
        )
        if golden.is_negative:
            negatives_total += 1
            if not evidence:
                negatives_empty += 1
            continue

        positives_total += 1
        observed = {item.doc_id for item in evidence}
        relevant = observed.intersection(golden.targets)
        if relevant:
            positives_hit += 1
        precisions.append(len(relevant) / len(observed) if observed else 0.0)

    return Metrics(
        recall_at_k=positives_hit / positives_total if positives_total else 0.0,
        precision_at_k=sum(precisions) / positives_total if positives_total else 0.0,
        negative_empty_rate=(
            negatives_empty / negatives_total if negatives_total else 0.0
        ),
        positives_hit=positives_hit,
        positives_total=positives_total,
        negatives_empty=negatives_empty,
        negatives_total=negatives_total,
    )


def _apply_thresholds(
    evidence: Sequence[Evidence],
    min_score: float,
    min_similarity: float | None,
    top_k: int = TOP_K,
) -> list[Evidence]:
    """Mirror ``retrieval._select``: relative cut-off, then absolute floor.

    ``retrieval`` applies ``min_score`` before ``min_similarity`` and keeps
    fused order, so the same order-preserving filter yields the same list.
    """
    selected = [
        item
        for item in evidence
        if item.score >= min_score
        and (min_similarity is None or item.similarity >= min_similarity)
    ]
    return selected[:top_k]


def recommend(
    golden_queries: Sequence[GoldenQuery],
    cache: dict[str, RetrievalResult],
) -> tuple[float, float, Metrics]:
    """Pick the thresholds that best separate positives from negatives.

    Among every ``(min_score, min_similarity)`` combination that still
    clears :data:`RECALL_TARGET`, the winner maximises the negative
    empty-rate, then Recall@5, then Precision@5, then prefers the lower
    thresholds.
    """
    best: tuple[float, float, Metrics] | None = None
    best_key: tuple[float, float, float, float, float] | None = None

    for min_similarity in MIN_SIMILARITY_GRID:
        for min_score in MIN_SCORE_GRID:
            metrics = evaluate(
                golden_queries,
                cache,
                min_score=min_score,
                min_similarity=min_similarity,
            )
            if not metrics.recall_ok:
                continue
            key = (
                metrics.negative_empty_rate,
                metrics.recall_at_k,
                metrics.precision_at_k,
                -min_similarity,
                -min_score,
            )
            if best_key is None or key > best_key:
                best_key = key
                best = (min_score, min_similarity, metrics)

    if best is None:
        fallback = evaluate(golden_queries, cache, min_score=0.0, min_similarity=None)
        return (0.0, 0.0, fallback)
    return best


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Render *rows* as a plain aligned text table."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: Sequence[str]) -> str:
        return "  ".join(
            cell.ljust(width) for cell, width in zip(cells, widths, strict=False)
        )

    rendered = [line(headers), line(["-" * width for width in widths])]
    rendered.extend(line(row) for row in rows)
    return "\n".join(rendered)


def _sweep_rows(
    golden_queries: Sequence[GoldenQuery],
    cache: dict[str, RetrievalResult],
    grid: Sequence[float],
    *,
    field: str,
) -> list[list[str]]:
    """Build the table rows for one threshold sweep."""
    rows: list[list[str]] = []
    for value in grid:
        thresholds = {"min_score": 0.0, "min_similarity": None}
        if field == "min_score":
            thresholds["min_score"] = value
        else:
            thresholds["min_similarity"] = value
        metrics = evaluate(golden_queries, cache, **thresholds)
        rows.append(
            [
                f"{value:.2f}",
                f"{metrics.recall_at_k:.3f}",
                f"{metrics.precision_at_k:.3f}",
                f"{metrics.negative_empty_rate:.3f}",
                "PASS" if metrics.recall_ok else "FAIL",
            ]
        )
    return rows


def _verdict(golden: GoldenQuery, observed: set[str]) -> str:
    """Per-query outcome label."""
    if golden.is_negative:
        return "OK" if not observed else "LEAK"
    return "HIT" if observed.intersection(golden.targets) else "MISS"


def _print_detail(
    golden_queries: Sequence[GoldenQuery],
    cache: dict[str, RetrievalResult],
    min_score: float,
    min_similarity: float | None,
) -> None:
    """Print one row per query for the given thresholds."""
    rows: list[list[str]] = []
    for golden in golden_queries:
        evidence = _apply_thresholds(
            cache[golden.query_id].evidence, min_score, min_similarity
        )
        observed = [item.doc_id for item in evidence]
        top_similarity = max((item.similarity for item in evidence), default=0.0)
        rows.append(
            [
                golden.query_id,
                _truncate(golden.text, 40),
                ", ".join(golden.targets) or "(none)",
                ", ".join(observed) or "-",
                f"{top_similarity:.3f}",
                _verdict(golden, set(observed)),
            ]
        )

    headers = ["ID", "QUERY", "TARGET", "TOP-5 DOC_IDS", "TOP-SIM", "OK"]
    print(render_table(headers, rows))


def _truncate(text: str, width: int) -> str:
    """Shorten *text* to *width* characters for table display."""
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation suite and return a process exit code."""
    parser = argparse.ArgumentParser(description="Retrieval evaluation suite.")
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=GOLDEN_SET_PATH,
        help="Path to the golden set YAML (default: %(default)s).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a per-query breakdown after the summary.",
    )
    args = parser.parse_args(argv)

    golden_queries = load_golden_set(args.golden_set)
    negatives = sum(1 for golden in golden_queries if golden.is_negative)
    positives = len(golden_queries) - negatives

    print("Retrieval evaluation")
    print(f"  golden set : {args.golden_set}")
    print(f"  queries    : {len(golden_queries)} ({positives} positive, {negatives} negative)")
    print(f"  metric     : Recall@{TOP_K} target >= {RECALL_TARGET:.2f}\n")

    cache = retrieve_all(golden_queries)
    degraded = sorted(
        query_id for query_id, result in cache.items() if result.degraded
    )
    if degraded:
        print(f"WARNING: retrieval degraded for {len(degraded)} query(ies):")
        print(f"  {', '.join(degraded)}")
        print("  Is the corpus ingested? python -m auditor.corpus ingest corpus/seed\n")

    print(f"[1] MIN_SCORE sweep (MIN_SIMILARITY = none, baseline = {DEFAULT_MIN_SCORE:.2f})")
    score_rows = _sweep_rows(
        golden_queries, cache, MIN_SCORE_GRID, field="min_score"
    )
    baseline = evaluate(
        golden_queries, cache, min_score=DEFAULT_MIN_SCORE, min_similarity=None
    )
    score_rows.append(
        [
            f"{DEFAULT_MIN_SCORE:.2f}",
            f"{baseline.recall_at_k:.3f}",
            f"{baseline.precision_at_k:.3f}",
            f"{baseline.negative_empty_rate:.3f}",
            "PASS" if baseline.recall_ok else "FAIL",
        ]
    )
    print(
        render_table(
            ["MIN_SCORE", "RECALL@5", "PREC@5", "NEG-EMPTY", "VERDICT"],
            score_rows,
        )
    )

    print("\n[2] MIN_SIMILARITY sweep (MIN_SCORE = 0.00)")
    print(
        render_table(
            ["MIN_SIMILARITY", "RECALL@5", "PREC@5", "NEG-EMPTY", "VERDICT"],
            _sweep_rows(
                golden_queries, cache, MIN_SIMILARITY_GRID, field="min_similarity"
            ),
        )
    )

    min_score, min_similarity, metrics = recommend(golden_queries, cache)
    print("\n[3] Recommended configuration")
    print(f"  MIN_SCORE      = {min_score:.2f}")
    print(f"  MIN_SIMILARITY = {min_similarity:.2f}")
    print(
        render_table(
            ["METRIC", "VALUE", "DETAIL"],
            [
                [
                    "Recall@5",
                    f"{metrics.recall_at_k:.3f}",
                    (
                        f"{metrics.positives_hit}/{metrics.positives_total}"
                        f" (target >= {RECALL_TARGET:.2f})"
                    ),
                ],
                [
                    "Precision@5",
                    f"{metrics.precision_at_k:.3f}",
                    "mean share of top-5 documents that are targets",
                ],
                [
                    "Neg-Empty-Rate",
                    f"{metrics.negative_empty_rate:.3f}",
                    (
                        f"{metrics.negatives_empty}/{metrics.negatives_total}"
                        " negative queries returned no evidence"
                    ),
                ],
            ],
        )
    )
    print(f"\nRESULT: {'PASS' if metrics.recall_ok else 'FAIL'}")

    if args.verbose:
        print(f"\n[4] Per-query detail (MIN_SCORE={min_score:.2f}, "
              f"MIN_SIMILARITY={min_similarity:.2f})")
        _print_detail(golden_queries, cache, min_score, min_similarity)

    return 0 if metrics.recall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
