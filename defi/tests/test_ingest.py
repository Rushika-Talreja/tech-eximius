from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models

from auditor_core.rag.ingest import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
    CorpusError,
    build_records,
    ingest,
    load_corpus,
)

VALID_DOC = """\
doc_id: swc-999
kind: swc
title: Example Vulnerability
vuln_class:
  - example-class
swc_ids:
  - SWC-999
source_url: https://example.com/SWC-999
license: MIT
date: null
loss_usd: null
summary: A short summary of the example vulnerability.
root_cause: The example has a root cause.
exploit_pattern: The example is exploited like this.
remediation: The example is fixed like this.
excerpts: []
"""


def write_doc(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_file_produces_five_records(tmp_path: Path) -> None:
    write_doc(tmp_path, "swc-999.yaml", VALID_DOC)

    docs = load_corpus(tmp_path)
    assert len(docs) == 1

    records = build_records(docs[0])
    assert len(records) == 5
    assert [r["chunk_id"] for r in records] == [
        "swc-999:taxonomy",
        "swc-999:incident",
        "swc-999:root_cause",
        "swc-999:exploit_pattern",
        "swc-999:remediation",
    ]
    assert [r["level"] for r in records] == [
        "taxonomy",
        "incident",
        "chunk",
        "chunk",
        "chunk",
    ]
    for record in records:
        assert record["doc_id"] == "swc-999"
        assert record["swc_ids"] == ["SWC-999"]
        assert record["vuln_class"] == ["example-class"]
        assert record["source_url"] == "https://example.com/SWC-999"
        assert record["license"] == "MIT"
        assert len(record["content_hash"]) == 64

    assert records[0]["text"] == "example-class"
    assert records[1]["text"].startswith("Example Vulnerability")
    assert records[2]["text"] == "The example has a root cause."


def test_missing_field_raises_error(tmp_path: Path) -> None:
    broken = VALID_DOC.replace("root_cause: The example has a root cause.\n", "")
    write_doc(tmp_path, "broken.yaml", broken)

    with pytest.raises(CorpusError) as excinfo:
        load_corpus(tmp_path)

    message = str(excinfo.value)
    assert "broken.yaml" in message
    assert "root_cause" in message


def test_running_twice_is_deterministic(tmp_path: Path) -> None:
    write_doc(tmp_path, "swc-999.yaml", VALID_DOC)

    first = build_records(load_corpus(tmp_path)[0])
    second = build_records(load_corpus(tmp_path)[0])

    assert [r["chunk_id"] for r in first] == [r["chunk_id"] for r in second]
    assert [r["content_hash"] for r in first] == [r["content_hash"] for r in second]


class StubEmbedder:
    """Deterministic stand-in for fastembed so tests need no model download."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed(self, texts) -> list[tuple[list[float], models.SparseVector]]:
        pairs = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            dense = [0.0] * self.dim
            dense[digest[0] % self.dim] = 1.0
            dense[digest[1] % self.dim] = 1.0
            pairs.append(
                (
                    dense,
                    models.SparseVector(
                        indices=[int(digest[2]), int(digest[3])],
                        values=[1.0, 1.0],
                    ),
                )
            )
        return pairs


def seed_corpus(tmp_path: Path) -> Path:
    corpus_dir = tmp_path / "seed"
    corpus_dir.mkdir()
    write_doc(corpus_dir, "swc-999.yaml", VALID_DOC)
    return corpus_dir


def test_ingest_twice_keeps_five_points(tmp_path: Path) -> None:
    corpus_dir = seed_corpus(tmp_path)
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    embedder = StubEmbedder()

    first = ingest(
        corpus_dir,
        client=client,
        embedder=embedder,
        create_payload_indexes=False,
    )
    assert (first.documents, first.added, first.updated, first.skipped) == (1, 5, 0, 0)
    assert client.count(COLLECTION_NAME).count == 5

    second = ingest(
        corpus_dir,
        client=client,
        embedder=embedder,
        create_payload_indexes=False,
    )
    assert (second.added, second.updated, second.skipped) == (0, 0, 5)
    assert client.count(COLLECTION_NAME).count == 5
    client.close()


def test_changed_content_updates_existing_point(tmp_path: Path) -> None:
    corpus_dir = seed_corpus(tmp_path)
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    embedder = StubEmbedder()

    ingest(corpus_dir, client=client, embedder=embedder, create_payload_indexes=False)

    write_doc(
        corpus_dir,
        "swc-999.yaml",
        VALID_DOC.replace(
            "The example has a root cause.", "A rewritten root cause sentence."
        ),
    )
    stats = ingest(
        corpus_dir,
        client=client,
        embedder=embedder,
        create_payload_indexes=False,
    )

    assert (stats.added, stats.updated, stats.skipped) == (0, 1, 4)
    assert client.count(COLLECTION_NAME).count == 5
    client.close()
