"""Index text/markdown files into the SQLite hybrid index."""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlite_vec

from sqlite_rag_mcp import chunker, embeddings
from sqlite_rag_mcp.config import settings
from sqlite_rag_mcp.db import delete_document_chunks, get_conn

log = logging.getLogger(__name__)

_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_EMBED_BATCH_SIZE = 16


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _title_of(text: str, fallback: str) -> str:
    m = _HEADING.search(text)
    return m.group(1).strip() if m else fallback


def _embed_chunks(
    conn: sqlite3.Connection, chunk_ids: list[int], texts: list[str]
) -> int:
    """Embed chunk texts and store vectors. Returns number of vectors stored."""
    stored = 0
    for start in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch_ids = chunk_ids[start : start + _EMBED_BATCH_SIZE]
        batch_texts = texts[start : start + _EMBED_BATCH_SIZE]
        vectors = embeddings.embed_batch(batch_texts)
        for cid, vec in zip(batch_ids, vectors):
            conn.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (cid, sqlite_vec.serialize_float32(vec)),
            )
            stored += 1
    return stored


def index_directory(
    root: Path | str,
    glob: str = "**/*.md",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Index every file under ``root`` matching ``glob``.

    Files are chunked, stored, FTS-indexed, and (when Ollama is reachable)
    embedded. Unchanged files (same SHA-256) are skipped. If Ollama is down,
    indexing still succeeds — chunks are searchable lexically and a warning
    is included in the returned stats.
    """
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    conn = get_conn(db_path)
    use_embeddings = embeddings.is_available(force=True)

    indexed = 0
    skipped_unchanged = 0
    skipped_unreadable = 0
    chunk_count = 0
    embedded_count = 0
    warnings: list[str] = []

    if not use_embeddings:
        warnings.append(
            f"Ollama not reachable at {settings.ollama_host}: documents were "
            "indexed WITHOUT embeddings (lexical search only). Re-run "
            "index_documents once Ollama is up to enable semantic search."
        )

    for file in sorted(p for p in root.glob(glob) if p.is_file()):
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            log.warning("skipping unreadable file %s: %s", file, exc)
            skipped_unreadable += 1
            continue
        if not text.strip():
            skipped_unreadable += 1
            continue

        digest = _sha256(text)
        rel_path = str(file)
        row = conn.execute(
            "SELECT id, sha256 FROM documents WHERE path = ?", (rel_path,)
        ).fetchone()
        if row and row["sha256"] == digest:
            skipped_unchanged += 1
            continue

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        title = _title_of(text, file.stem)
        if row:
            doc_id = row["id"]
            delete_document_chunks(conn, doc_id)
            conn.execute(
                "UPDATE documents SET sha256 = ?, title = ?, indexed_at = ? WHERE id = ?",
                (digest, title, now, doc_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO documents(path, title, sha256, indexed_at) VALUES (?, ?, ?, ?)",
                (rel_path, title, digest, now),
            )
            doc_id = cur.lastrowid

        chunk_texts = chunker.split(text)
        chunk_ids: list[int] = []
        for seq, chunk_text in enumerate(chunk_texts):
            cur = conn.execute(
                "INSERT INTO chunks(doc_id, seq, text) VALUES (?, ?, ?)",
                (doc_id, seq, chunk_text),
            )
            cid = cur.lastrowid
            assert cid is not None
            conn.execute(
                "INSERT INTO fts_chunks(rowid, text) VALUES (?, ?)",
                (cid, chunk_text),
            )
            chunk_ids.append(cid)

        if use_embeddings and chunk_ids:
            try:
                embedded_count += _embed_chunks(conn, chunk_ids, chunk_texts)
            except embeddings.EmbeddingUnavailableError as exc:
                # Ollama went away mid-run: keep indexing lexically.
                use_embeddings = False
                warnings.append(
                    f"embeddings failed mid-indexing ({exc}); remaining files "
                    "were indexed without embeddings."
                )

        conn.commit()
        indexed += 1
        chunk_count += len(chunk_ids)
        log.info("indexed %s (%d chunks)", file, len(chunk_ids))

    conn.close()
    return {
        "root": str(root),
        "glob": glob,
        "files_indexed": indexed,
        "files_skipped_unchanged": skipped_unchanged,
        "files_skipped_unreadable": skipped_unreadable,
        "chunks_added": chunk_count,
        "chunks_embedded": embedded_count,
        "warnings": warnings,
    }
