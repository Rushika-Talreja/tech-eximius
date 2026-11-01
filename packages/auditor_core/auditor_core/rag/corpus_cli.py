"""Corpus CLI: ingest a corpus folder into Qdrant."""

from __future__ import annotations

import argparse
import sys

from auditor_core.rag.ingest import CorpusError, ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auditor-corpus")
    sub = parser.add_subparsers(dest="command", required=True)
    p_ingest = sub.add_parser("ingest", help="Ingest a corpus folder into Qdrant")
    p_ingest.add_argument("folder", help="Folder with corpus YAML files")
    args = parser.parse_args(argv)

    if args.command == "ingest":
        try:
            stats = ingest(args.folder)
        except CorpusError as exc:
            print(f"Corpus error: {exc}", file=sys.stderr)
            return 1
        print(stats)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())