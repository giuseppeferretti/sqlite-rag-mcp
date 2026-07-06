"""MCP server exposing the SQLite hybrid-RAG index over stdio.

Tools:
    index_documents(path, glob) — index text/markdown files from a directory
    search(query, k, mode)      — hybrid / semantic / lexical search
    get_chunk(chunk_id)         — full text of one chunk
    stats()                     — index counters and configuration
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from sqlite_rag_mcp import embeddings, search as search_mod
from sqlite_rag_mcp.config import settings
from sqlite_rag_mcp.db import get_conn
from sqlite_rag_mcp.indexer import index_directory

log = logging.getLogger(__name__)

_SNIPPET_CHARS = 300

mcp = FastMCP(
    "sqlite-rag",
    instructions=(
        "100% offline document search. Index local text/markdown files into "
        "SQLite (sqlite-vec + FTS5) with index_documents, then query them "
        "with search (hybrid RRF by default). Use get_chunk to read a full "
        "chunk and stats to inspect the index. Documents never leave the "
        "machine; embeddings are computed by a local Ollama instance and "
        "search degrades gracefully to lexical FTS5 when Ollama is offline."
    ),
)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= _SNIPPET_CHARS:
        return text
    return text[:_SNIPPET_CHARS].rsplit(" ", 1)[0] + " …"


def run_search(
    query: str,
    k: int = 8,
    mode: str = "hybrid",
) -> dict[str, Any]:
    """Core search logic (also used directly by tests)."""
    if mode not in ("hybrid", "semantic", "lexical"):
        raise ValueError(f"invalid mode {mode!r}; use hybrid, semantic or lexical")
    k = max(1, min(int(k), 50))
    conn = get_conn()
    warning: str | None = None
    mode_used = mode

    query_vec: list[float] | None = None
    if mode in ("hybrid", "semantic"):
        if embeddings.is_available():
            try:
                query_vec = embeddings.embed(query)
            except embeddings.EmbeddingUnavailableError as exc:
                log.warning("query embedding failed: %s", exc)
        if query_vec is None:
            mode_used = "lexical"
            warning = (
                f"Ollama not reachable at {settings.ollama_host}; fell back "
                "to lexical (FTS5) search. Start Ollama and pull the "
                f"'{settings.embed_model}' model to enable "
                f"{mode} search."
            )

    if mode_used == "semantic":
        assert query_vec is not None
        hits = search_mod.semantic_search(conn, query_vec, top_k=k)
    elif mode_used == "hybrid":
        assert query_vec is not None
        hits = search_mod.hybrid_search(conn, query, query_vec, top_k=k)
    else:
        hits = search_mod.lexical_search(conn, query, top_k=k)

    results = []
    for hit in hits:
        doc = conn.execute(
            "SELECT path, title FROM documents WHERE id = ?", (hit["doc_id"],)
        ).fetchone()
        results.append(
            {
                "chunk_id": hit["rowid"],
                "score": round(hit["score"], 6),
                "snippet": _snippet(hit["text"]),
                "source": doc["path"] if doc else None,
                "title": doc["title"] if doc else None,
                "chunk_seq": hit["seq"],
                "matched_by": hit["matched_by"],
            }
        )
    conn.close()

    out: dict[str, Any] = {
        "query": query,
        "mode_requested": mode,
        "mode_used": mode_used,
        "results": results,
    }
    if warning:
        out["warning"] = warning
    return out


def run_get_chunk(chunk_id: int) -> dict[str, Any]:
    """Core get_chunk logic (also used directly by tests)."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT c.id, c.seq, c.text, d.path, d.title
        FROM chunks c JOIN documents d ON d.id = c.doc_id
        WHERE c.id = ?
        """,
        (chunk_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return {"found": False, "chunk_id": chunk_id}
    return {
        "found": True,
        "chunk_id": row["id"],
        "chunk_seq": row["seq"],
        "source": row["path"],
        "title": row["title"],
        "text": row["text"],
    }


def run_stats() -> dict[str, Any]:
    """Core stats logic (also used directly by tests)."""
    conn = get_conn()
    documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    embedded = conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0]
    conn.close()
    db_path = settings.db_path
    return {
        "db_path": str(db_path),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "documents": documents,
        "chunks": chunks,
        "chunks_embedded": embedded,
        "embed_model": settings.embed_model,
        "ollama_host": settings.ollama_host,
        "ollama_available": embeddings.is_available(force=True),
    }


@mcp.tool()
def index_documents(path: str, glob: str = "**/*.md") -> dict[str, Any]:
    """Index text/markdown files from a directory into the local SQLite index.

    Args:
        path: Directory to index (absolute or ~-expanded).
        glob: Glob pattern relative to the directory (default '**/*.md').
              Use e.g. '**/*.txt' or '**/*' for other text files.
    """
    return index_directory(path, glob=glob)


@mcp.tool()
def search(
    query: str,
    k: int = 8,
    mode: Literal["hybrid", "semantic", "lexical"] = "hybrid",
) -> dict[str, Any]:
    """Search the indexed documents.

    Args:
        query: Natural-language query or keywords.
        k: Number of results to return (1-50, default 8).
        mode: 'hybrid' (RRF fusion of semantic + lexical, default),
              'semantic' (vector KNN only), or 'lexical' (FTS5 BM25 only).
              If Ollama is offline, hybrid/semantic fall back to lexical and
              a warning is included in the response.
    """
    return run_search(query, k=k, mode=mode)


@mcp.tool()
def get_chunk(chunk_id: int) -> dict[str, Any]:
    """Fetch the full text and source of a chunk returned by search."""
    return run_get_chunk(chunk_id)


@mcp.tool()
def stats() -> dict[str, Any]:
    """Index statistics: document/chunk/embedding counts and configuration."""
    return run_stats()


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
