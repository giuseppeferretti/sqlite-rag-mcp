"""End-to-end index + search tests for both paths: Ollama up (faked) and down."""
from __future__ import annotations

from sqlite_rag_mcp.indexer import index_directory
from sqlite_rag_mcp.server import run_get_chunk, run_search, run_stats

from .conftest import FIXTURES_DIR

N_FIXTURES = 7


# ---------------------------------------------------------------- Ollama DOWN


def test_index_without_ollama_warns_but_succeeds(tmp_db, no_ollama):
    stats = index_directory(FIXTURES_DIR)
    assert stats["files_indexed"] == N_FIXTURES
    assert stats["chunks_added"] > 0
    assert stats["chunks_embedded"] == 0
    assert any("Ollama not reachable" in w for w in stats["warnings"])


def test_hybrid_falls_back_to_lexical_when_ollama_down(tmp_db, no_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("kubernetes readiness probe", k=5, mode="hybrid")
    assert out["mode_requested"] == "hybrid"
    assert out["mode_used"] == "lexical"
    assert "warning" in out and "lexical" in out["warning"]
    assert out["results"], "fallback search must still return results"
    assert out["results"][0]["source"].endswith("deployment.md")


def test_semantic_falls_back_to_lexical_when_ollama_down(tmp_db, no_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("cache invalidation strategies", k=5, mode="semantic")
    assert out["mode_used"] == "lexical"
    assert "warning" in out
    assert out["results"][0]["source"].endswith("caching.md")


def test_explicit_lexical_mode_has_no_warning(tmp_db, no_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("oauth device flow token", k=3, mode="lexical")
    assert out["mode_used"] == "lexical"
    assert "warning" not in out
    assert out["results"][0]["source"].endswith("authentication.md")


def test_malformed_query_never_raises(tmp_db, no_ollama):
    index_directory(FIXTURES_DIR)
    for query in ['"unbalanced AND (', "---", "e-mails*", "   ", "NOT OR"]:
        out = run_search(query, mode="lexical")
        assert isinstance(out["results"], list)


# ------------------------------------------------------------------ Ollama UP


def test_index_with_embeddings(tmp_db, fake_ollama):
    stats = index_directory(FIXTURES_DIR)
    assert stats["files_indexed"] == N_FIXTURES
    assert stats["chunks_embedded"] == stats["chunks_added"] > 0
    assert stats["warnings"] == []


def test_semantic_search(tmp_db, fake_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("cache invalidation TTL versioned keys", k=5, mode="semantic")
    assert out["mode_used"] == "semantic"
    assert "warning" not in out
    assert out["results"][0]["source"].endswith("caching.md")
    assert out["results"][0]["matched_by"] == "semantic"


def test_hybrid_search_fuses_both_rankers(tmp_db, fake_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("docker kubernetes deployment probes", k=5, mode="hybrid")
    assert out["mode_used"] == "hybrid"
    assert out["results"][0]["source"].endswith("deployment.md")
    assert any(
        r["matched_by"] == "semantic+lexical" for r in out["results"]
    ), "top hits should be found by both rankers"


def test_reindex_skips_unchanged_files(tmp_db, fake_ollama):
    first = index_directory(FIXTURES_DIR)
    second = index_directory(FIXTURES_DIR)
    assert first["files_indexed"] == N_FIXTURES
    assert second["files_indexed"] == 0
    assert second["files_skipped_unchanged"] == N_FIXTURES
    assert run_stats()["documents"] == N_FIXTURES  # no duplicates


def test_get_chunk_returns_full_text(tmp_db, fake_ollama):
    index_directory(FIXTURES_DIR)
    out = run_search("scrypt hashed tokens", k=1, mode="lexical")
    chunk_id = out["results"][0]["chunk_id"]
    chunk = run_get_chunk(chunk_id)
    assert chunk["found"] is True
    assert chunk["chunk_id"] == chunk_id
    assert "scrypt" in chunk["text"]
    assert chunk["source"].endswith("authentication.md")


def test_get_chunk_missing_id(tmp_db, fake_ollama):
    index_directory(FIXTURES_DIR)
    assert run_get_chunk(999999) == {"found": False, "chunk_id": 999999}


def test_stats(tmp_db, fake_ollama):
    index_directory(FIXTURES_DIR)
    s = run_stats()
    assert s["documents"] == N_FIXTURES
    assert s["chunks"] > 0
    assert s["chunks_embedded"] == s["chunks"]
    assert s["db_size_bytes"] > 0
    assert str(tmp_db) == s["db_path"]
