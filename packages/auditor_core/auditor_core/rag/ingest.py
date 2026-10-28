"""Corpus loading, chunking and Qdrant ingestion for the auditor RAG pipeline.

Documents are loaded from YAML, split into chunk records, embedded with
fastembed (dense + sparse) and upserted into the ``security_postmortems``
Qdrant collection. Ingestion is idempotent: point IDs are derived from the
chunk ID and chunks whose ``content_hash`` is unchanged are skipped.

Only the payload holds the untouched text. The vectorised text is prefixed
with an identifier header (doc id, SWC ids, vuln classes, title) so keyword
search can match an exact SWC id, which lives in the payload alone.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

__all__ = [
    "CHUNK_FIELDS",
    "COLLECTION_NAME",
    "DENSE_VECTOR_NAME",
    "REQUIRED_FIELDS",
    "SPARSE_VECTOR_NAME",
    "CorpusError",
    "Embedder",
    "IngestStats",
    "build_records",
    "ensure_collection",
    "get_client",
    "ingest",
    "load_corpus",
]

#: Fields every corpus document must define.
REQUIRED_FIELDS = (
    "doc_id",
    "kind",
    "title",
    "vuln_class",
    "source_url",
    "license",
    "summary",
    "root_cause",
    "exploit_pattern",
    "remediation",
)

#: Fields that each become their own chunk record.
CHUNK_FIELDS = ("root_cause", "exploit_pattern", "remediation")

LEVEL_TAXONOMY = "taxonomy"
LEVEL_INCIDENT = "incident"
LEVEL_CHUNK = "chunk"


class CorpusError(ValueError):
    """Raised when a corpus document is malformed or incomplete."""


def load_corpus(folder: str | Path) -> list[dict[str, Any]]:
    """Read every ``*.yaml`` file in *folder* and return a list of dicts.

    Raises:
        FileNotFoundError: if *folder* does not exist.
        CorpusError: if a file is empty, is not a YAML mapping, or is missing
            one of :data:`REQUIRED_FIELDS`. The message names the file and
            the offending field.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"corpus folder not found: {folder}")

    docs: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            raise CorpusError(f"{path.name}: file is empty")
        if not isinstance(raw, dict):
            raise CorpusError(
                f"{path.name}: expected a YAML mapping, got {type(raw).__name__}"
            )
        for field in REQUIRED_FIELDS:
            value = raw.get(field)
            if field not in raw or value is None or value == "":
                raise CorpusError(f"{path.name}: missing required field '{field}'")
        docs.append(raw)
    return docs


def _content_hash(text: str) -> str:
    """Return the sha256 hex digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record(doc: dict[str, Any], *, chunk_id: str, level: str, text: str) -> dict[str, Any]:
    text = text.strip()
    # The identifiers only exist in the payload, so BM25 could never match an
    # exact SWC id. The header carries them into the embedded text instead.
    embedded_text = (
        f"{str(doc['doc_id']).upper()}"
        f" | {', '.join(str(value) for value in doc.get('swc_ids') or [])}"
        f" | {', '.join(str(value) for value in doc['vuln_class'])}"
        f" | {doc['title']}\n{text}"
    )
    return {
        "doc_id": doc["doc_id"],
        "chunk_id": chunk_id,
        "level": level,
        "vuln_class": list(doc["vuln_class"]),
        "swc_ids": list(doc.get("swc_ids") or []),
        "source_url": doc["source_url"],
        "license": doc["license"],
        "text": text,
        "embedded_text": embedded_text,
        "content_hash": _content_hash(embedded_text),
    }


def build_records(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn one corpus document into exactly five chunk records.

    Layout: one taxonomy record, one incident record, and one chunk record
    for each of :data:`CHUNK_FIELDS`.
    """
    doc_id = doc["doc_id"]
    records = [
        _record(
            doc,
            chunk_id=f"{doc_id}:taxonomy",
            level=LEVEL_TAXONOMY,
            text=", ".join(str(value) for value in doc["vuln_class"]),
        ),
        _record(
            doc,
            chunk_id=f"{doc_id}:incident",
            level=LEVEL_INCIDENT,
            text=f"{doc['title']}\n\n{doc['summary']}",
        ),
    ]
    for field in CHUNK_FIELDS:
        records.append(
            _record(
                doc,
                chunk_id=f"{doc_id}:{field}",
                level=LEVEL_CHUNK,
                text=str(doc[field]),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "security_postmortems"

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
SPARSE_MODEL = os.getenv("SPARSE_MODEL", "Qdrant/bm25")

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_LOCAL_PATH = "./qdrant_data"

#: Payload fields indexed as keywords. Only supported by a Qdrant server.
PAYLOAD_INDEX_FIELDS = ("vuln_class", "level", "source_type")

#: Namespace used to derive stable point IDs from chunk IDs.
POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "auditor.core/rag/ingest")

EMBED_BATCH_SIZE = 64


class Embedder:
    """Dense and sparse (BM25) embeddings produced by fastembed."""

    def __init__(
        self,
        dense_model: str | None = None,
        sparse_model: str | None = None,
    ) -> None:
        started = time.perf_counter()
        self.dense = TextEmbedding(model_name=dense_model or EMBEDDING_MODEL)
        self.sparse = SparseTextEmbedding(model_name=sparse_model or SPARSE_MODEL)
        logger.info(
            "embedding models ready: model=%s dim=%d sparse_model=%s elapsed=%.3fs",
            dense_model or EMBEDDING_MODEL,
            EMBEDDING_DIM,
            sparse_model or SPARSE_MODEL,
            time.perf_counter() - started,
        )

    def embed(self, texts: Sequence[str]) -> list[tuple[list[float], models.SparseVector]]:
        """Return one ``(dense_vector, sparse_vector)`` pair per input text."""
        documents = list(texts)
        dense_vectors = list(self.dense.embed(documents))
        sparse_vectors = list(self.sparse.embed(documents))
        return [
            (
                [float(value) for value in dense],
                models.SparseVector(
                    indices=[int(index) for index in sparse.indices],
                    values=[float(value) for value in sparse.values],
                ),
            )
            for dense, sparse in zip(dense_vectors, sparse_vectors)
        ]


@dataclass(frozen=True)
class IngestStats:
    """Outcome counters for one ingestion run."""

    documents: int
    added: int
    updated: int
    skipped: int
    elapsed_seconds: float

    @property
    def upserted(self) -> int:
        return self.added + self.updated


def get_client(url: str | None = None, path: str | Path | None = None) -> QdrantClient:
    """Return a Qdrant client.

    A remote server is used when *url* (or the ``QDRANT_URL`` environment
    variable) is set, otherwise local on-disk mode at *path*, which defaults
    to ``./qdrant_data``.
    """
    url = url if url is not None else QDRANT_URL
    if url:
        logger.info("connecting to remote Qdrant at %s", url)
        return QdrantClient(url=url)

    local_path = str(path if path is not None else QDRANT_LOCAL_PATH)
    logger.info("opening local Qdrant at %s", local_path)
    return QdrantClient(path=local_path)


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str = COLLECTION_NAME,
    create_payload_indexes: bool = False,
) -> bool:
    """Create the collection when missing; return True if it was created.

    Payload indexes are only created for a Qdrant server, because local mode
    does not support them.
    """
    if client.collection_exists(collection_name):
        return False

    started = time.perf_counter()
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            DENSE_VECTOR_NAME: models.VectorParams(
                size=EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={SPARSE_VECTOR_NAME: models.SparseVectorParams()},
    )

    if create_payload_indexes:
        for field in PAYLOAD_INDEX_FIELDS:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    logger.info(
        "created collection %s: dense=%s(%d, cosine) sparse=%s payload_indexes=%s elapsed=%.3fs",
        collection_name,
        DENSE_VECTOR_NAME,
        EMBEDDING_DIM,
        SPARSE_VECTOR_NAME,
        create_payload_indexes,
        time.perf_counter() - started,
    )
    return True


def _point_id(chunk_id: str) -> str:
    """Stable point ID for a chunk, so re-runs update instead of duplicate."""
    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def _payload(doc: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Build the stored payload for one record."""
    return {
        "doc_id": record["doc_id"],
        "chunk_id": record["chunk_id"],
        "level": record["level"],
        "vuln_class": list(record["vuln_class"]),
        "swc_ids": list(record["swc_ids"]),
        "cwe_ids": list(doc.get("cwe_ids") or []),
        "incident_name": doc.get("incident_name"),
        "date": doc.get("date"),
        "loss_usd": doc.get("loss_usd"),
        "source_url": record["source_url"],
        "source_type": doc.get("source_type") or doc.get("kind"),
        "license": record["license"],
        "content_hash": record["content_hash"],
        "text": record["text"],
    }


def ingest(
    folder: str | Path,
    *,
    client: QdrantClient | None = None,
    embedder: Any | None = None,
    collection_name: str = COLLECTION_NAME,
    create_payload_indexes: bool | None = None,
) -> IngestStats:
    """Load, chunk, embed and upsert a corpus folder into Qdrant.

    *embedder* only needs an ``embed(texts)`` method; it defaults to
    :class:`Embedder` and is only constructed when something actually needs
    to be written.
    """
    started = time.perf_counter()
    docs = load_corpus(folder)

    if create_payload_indexes is None:
        create_payload_indexes = bool(QDRANT_URL)

    client = client or get_client()
    ensure_collection(
        client,
        collection_name=collection_name,
        create_payload_indexes=create_payload_indexes,
    )

    pairs = [(doc, record) for doc in docs for record in build_records(doc)]
    point_ids = [_point_id(record["chunk_id"]) for _, record in pairs]

    stored_hashes: dict[str, Any] = {}
    if point_ids:
        for point in client.retrieve(
            collection_name=collection_name,
            ids=point_ids,
            with_payload=["content_hash"],
            with_vectors=False,
        ):
            stored_hashes[str(point.id)] = (point.payload or {}).get("content_hash")

    pending: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    added = updated = skipped = 0
    for (doc, record), point_id in zip(pairs, point_ids):
        stored_hash = stored_hashes.get(point_id)
        if stored_hash == record["content_hash"]:
            skipped += 1
            logger.debug("skipped unchanged chunk_id=%s", record["chunk_id"])
            continue
        if stored_hash is None:
            added += 1
        else:
            updated += 1
        pending.append((point_id, doc, record))

    if pending:
        embedder = embedder or Embedder()
        embed_started = time.perf_counter()
        for start in range(0, len(pending), EMBED_BATCH_SIZE):
            batch = pending[start : start + EMBED_BATCH_SIZE]
            vectors = embedder.embed([record["embedded_text"] for _, _, record in batch])
            points = [
                models.PointStruct(
                    id=point_id,
                    vector={DENSE_VECTOR_NAME: dense, SPARSE_VECTOR_NAME: sparse},
                    payload=_payload(doc, record),
                )
                for (point_id, doc, record), (dense, sparse) in zip(batch, vectors)
            ]
            client.upsert(collection_name=collection_name, points=points, wait=True)
            logger.debug(
                "upserted %d point(s) ids=%s",
                len(points),
                [point.id for point in points],
            )
        logger.info(
            "embedded and upserted %d point(s) in %.3fs",
            len(pending),
            time.perf_counter() - embed_started,
        )

    stats = IngestStats(
        documents=len(docs),
        added=added,
        updated=updated,
        skipped=skipped,
        elapsed_seconds=time.perf_counter() - started,
    )
    logger.info(
        "ingest finished: documents=%d added=%d updated=%d skipped=%d elapsed=%.3fs",
        stats.documents,
        stats.added,
        stats.updated,
        stats.skipped,
        stats.elapsed_seconds,
    )
    return stats
