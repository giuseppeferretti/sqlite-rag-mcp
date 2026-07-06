"""SQLite connection management and schema.

The index lives in a single SQLite file with three companion structures:

- ``documents`` / ``chunks``: plain relational tables.
- ``vec_chunks``: a `sqlite-vec <https://github.com/asg017/sqlite-vec>`_ vec0
  virtual table for vector KNN search. Its rowid mirrors ``chunks.id``.
- ``fts_chunks``: an FTS5 external-content table over ``chunks`` for BM25
  lexical search. Its rowid also mirrors ``chunks.id``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from sqlite_rag_mcp.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    title TEXT,
    sha256 TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{dim}]);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (and initialize, if needed) the index database."""
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
        conn.executescript(SCHEMA.format(dim=settings.embed_dim))
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    return conn


def delete_document_chunks(conn: sqlite3.Connection, doc_id: int) -> None:
    """Remove all chunks of a document from chunks, FTS5 and vec tables."""
    rows = conn.execute(
        "SELECT id, text FROM chunks WHERE doc_id = ?", (doc_id,)
    ).fetchall()
    for row in rows:
        # External-content FTS5 requires the special 'delete' command.
        conn.execute(
            "INSERT INTO fts_chunks(fts_chunks, rowid, text) VALUES ('delete', ?, ?)",
            (row["id"], row["text"]),
        )
        conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (row["id"],))
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
