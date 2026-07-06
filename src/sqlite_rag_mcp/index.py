"""Standalone indexing CLI: ``python -m sqlite_rag_mcp.index <dir>``.

Useful for building or refreshing the index outside of an MCP session
(e.g. from cron or a shell script).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlite_rag_mcp.indexer import index_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sqlite_rag_mcp.index",
        description="Index text/markdown files into the local SQLite RAG index.",
    )
    parser.add_argument("directory", help="directory containing the files to index")
    parser.add_argument(
        "--glob",
        default="**/*.md",
        help="glob pattern relative to the directory (default: **/*.md)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="database path (default: $SQLITE_RAG_DB or "
        "~/.local/share/sqlite-rag-mcp/index.db)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")

    stats = index_directory(
        args.directory,
        glob=args.glob,
        db_path=Path(args.db).expanduser() if args.db else None,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
