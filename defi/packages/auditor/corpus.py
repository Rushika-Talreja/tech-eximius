"""``python -m auditor.corpus`` command-line entry point.

Usage::

    python -m auditor.corpus ingest corpus/seed --dry-run   # print records only
    python -m auditor.corpus ingest corpus/seed             # embed and upsert
"""

from __future__ import annotations

import argparse
import logging
import sys

from auditor_core.rag.ingest import build_records, ingest, load_corpus

PREVIEW_CHARS = 60


def _print_records(folder: str) -> int:
    record_count = 0
    for doc in load_corpus(folder):
        for record in build_records(doc):
            preview = record["text"][:PREVIEW_CHARS].replace("\n", " ")
            print(f"{record['chunk_id']}\t{record['level']}\t{preview}")
            record_count += 1
    return record_count


def _cmd_ingest(folder: str, dry_run: bool) -> int:
    if dry_run:
        record_count = _print_records(folder)
        print(f"{record_count} record(s) (dry run, nothing persisted)", file=sys.stderr)
        return 0

    stats = ingest(folder)
    print(
        f"ingest complete: {stats.documents} document(s), {stats.added} added, "
        f"{stats.updated} updated, {stats.skipped} skipped "
        f"({stats.elapsed_seconds:.2f}s)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auditor.corpus",
        description="Corpus tooling for the DeFi auditor.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="load and chunk corpus documents")
    ingest.add_argument("folder", help="folder containing the *.yaml corpus files")
    ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="only print the chunked records; do not embed or store anything",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _cmd_ingest(args.folder, args.dry_run)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
