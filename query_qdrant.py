"""Read-only inspection of the local Qdrant collection built by

``auditor_core.rag.ingest``. This script never writes to Qdrant and never
loads the dense embedding model.

Run from the repository root::

    venv\\Scripts\\python.exe query_qdrant.py
"""

from __future__ import annotations

from auditor_core.rag.ingest import (
    COLLECTION_NAME,
    QDRANT_LOCAL_PATH,
    SPARSE_MODEL,
    SPARSE_VECTOR_NAME,
)
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

DOC_ID = "swc-112"
QUERY = "SWC-112"
TOP_K = 5


def _show_points(client: QdrantClient) -> None:
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=DOC_ID),
                )
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )

    print(f"-- points with doc_id={DOC_ID} ({len(points)}) --")
    if not points:
        print("   (none found)")
        return
    for point in sorted(points, key=lambda p: str((p.payload or {}).get("level"))):
        payload = point.payload or {}
        print(f"   level={payload.get('level')}   chunk_id={payload.get('chunk_id')}")


def _query_vector(query: str) -> models.SparseVector:
    """Sparse query vector for *query*.

    ``ingest.py`` embeds passages with ``SparseTextEmbedding.embed``, so the
    matching method for a search string is ``query_embed``.
    """
    model = SparseTextEmbedding(model_name=SPARSE_MODEL)
    embedding = next(iter(model.query_embed(query)))
    return models.SparseVector(
        indices=[int(index) for index in embedding.indices],
        values=[float(value) for value in embedding.values],
    )


def main() -> int:
    client = QdrantClient(path=QDRANT_LOCAL_PATH)
    try:
        print(f"collection: {COLLECTION_NAME}")
        print(f"path: {QDRANT_LOCAL_PATH}")
        print(f"total points: {client.count(COLLECTION_NAME).count}")

        print()
        _show_points(client)

        print()
        vector = _query_vector(QUERY)
        print(f"-- sparse keyword search for {QUERY!r} --")
        print(f"   vector name: {SPARSE_VECTOR_NAME}   model: {SPARSE_MODEL}")
        print(f"   non-zero indices in query vector: {len(vector.indices)}")

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            using=SPARSE_VECTOR_NAME,
            limit=TOP_K,
            with_payload=True,
            with_vectors=False,
        )

        print(f"   top {TOP_K} hits:")
        if not response.points:
            print("     (no hits)")
            print(
                f"     note: {QUERY!r} tokenises to terms that appear in no chunk"
                " text, so BM25 has nothing to score"
            )
        for rank, point in enumerate(response.points, start=1):
            payload = point.payload or {}
            print(
                f"     {rank}. score={point.score:.4f}"
                f"   doc_id={payload.get('doc_id')}"
                f"   level={payload.get('level')}"
                f"   chunk_id={payload.get('chunk_id')}"
            )

        print()
        top_doc_id = (
            (response.points[0].payload or {}).get("doc_id")
            if response.points
            else None
        )
        if top_doc_id == DOC_ID:
            print("PASS")
            return 0
        print(f"FAIL (top hit doc_id={top_doc_id!r})")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
