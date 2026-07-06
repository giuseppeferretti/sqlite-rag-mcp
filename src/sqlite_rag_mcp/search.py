"""Hybrid search: FTS5 (BM25) + sqlite-vec KNN fused with Reciprocal Rank Fusion."""
from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from typing import Any

import sqlite_vec

log = logging.getLogger(__name__)

_RRF_K = 60  # standard RRF damping constant
_CANDIDATE_POOL = 30  # how many hits each ranker contributes before fusion
_TOKEN_CLEAN = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace (mirrors the FTS tokenizer)."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _rrf_score(rank: int) -> float:
    return 1.0 / (_RRF_K + rank + 1)


def lexical_search(
    conn: sqlite3.Connection, query: str, top_k: int = _CANDIDATE_POOL
) -> list[dict[str, Any]]:
    """BM25 search over the FTS5 index. Never raises on malformed queries."""
    # Sanitize each token: punctuation such as '-' or '"' would otherwise be
    # parsed as FTS5 operators (e.g. "e-mail*" becomes "e NOT mail*").
    tokens = []
    for raw in _normalize(query).split():
        t = _TOKEN_CLEAN.sub("", raw)
        if t:
            tokens.append(t + "*")
    if not tokens:
        return []
    # Explicit OR between tokens: FTS5 defaults to AND, which would require
    # every word to match. With OR, BM25 still ranks multi-term matches
    # higher, but partial matches remain reachable.
    fts_query = " OR ".join(tokens)
    try:
        rows = conn.execute(
            """
            SELECT f.rowid, rank, c.doc_id, c.seq, c.text
            FROM fts_chunks f
            JOIN chunks c ON c.id = f.rowid
            WHERE fts_chunks MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()
    except sqlite3.Error as exc:
        log.warning("FTS query failed (%r): %s", fts_query, exc)
        return []

    return [
        {
            "rowid": r["rowid"],
            # FTS5 rank is negative BM25 (lower = better) — map to positive score.
            "score": 1.0 / (1.0 - r["rank"] + 1.0),
            "doc_id": r["doc_id"],
            "seq": r["seq"],
            "text": r["text"],
            "matched_by": "lexical",
        }
        for r in rows
    ]


def semantic_search(
    conn: sqlite3.Connection, query_vec: list[float], top_k: int = _CANDIDATE_POOL
) -> list[dict[str, Any]]:
    """KNN search over the sqlite-vec index."""
    blob = sqlite_vec.serialize_float32(query_vec)
    rows = conn.execute(
        """
        SELECT vc.rowid, vc.distance, c.doc_id, c.seq, c.text
        FROM vec_chunks vc
        JOIN chunks c ON c.id = vc.rowid
        WHERE vc.embedding MATCH ?
          AND k = ?
        ORDER BY vc.distance
        """,
        (blob, top_k),
    ).fetchall()

    return [
        {
            "rowid": r["rowid"],
            "score": 1.0 / (1.0 + r["distance"]),
            "doc_id": r["doc_id"],
            "seq": r["seq"],
            "text": r["text"],
            "matched_by": "semantic",
        }
        for r in rows
    ]


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    query_vec: list[float],
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Fuse semantic and lexical rankings with Reciprocal Rank Fusion."""
    pool = max(_CANDIDATE_POOL, top_k * 3)
    sem_hits = semantic_search(conn, query_vec, top_k=pool)
    lex_hits = lexical_search(conn, query, top_k=pool)

    scores: dict[int, float] = {}
    meta: dict[int, dict[str, Any]] = {}

    for rank, hit in enumerate(sem_hits):
        rid = hit["rowid"]
        scores[rid] = scores.get(rid, 0.0) + _rrf_score(rank)
        meta[rid] = hit

    for rank, hit in enumerate(lex_hits):
        rid = hit["rowid"]
        scores[rid] = scores.get(rid, 0.0) + _rrf_score(rank)
        if rid in meta:
            meta[rid]["matched_by"] = "semantic+lexical"
        else:
            meta[rid] = hit

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

    results = []
    for rid, score in ranked:
        hit = dict(meta[rid])
        hit["score"] = score
        results.append(hit)
    return results
