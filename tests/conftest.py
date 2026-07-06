"""Shared fixtures: temp database, fake embedder, and Ollama on/off switches."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

from sqlite_rag_mcp import embeddings

FIXTURES_DIR = Path(__file__).parent / "fixtures"

EMBED_DIM = 768


def fake_vec(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic bag-of-words embedding: same words -> nearby vectors."""
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture
def tmp_db(tmp_path, monkeypatch) -> Path:
    """Point SQLITE_RAG_DB at a fresh temp file and reset the probe cache."""
    db = tmp_path / "index.db"
    monkeypatch.setenv("SQLITE_RAG_DB", str(db))
    monkeypatch.setattr(embeddings, "_available", None)
    return db


@pytest.fixture
def no_ollama(monkeypatch) -> None:
    """Simulate Ollama being offline."""
    monkeypatch.setattr(embeddings, "is_available", lambda force=False: False)

    def _fail(*args, **kwargs):
        raise embeddings.EmbeddingUnavailableError("ollama is offline (test)")

    monkeypatch.setattr(embeddings, "embed", _fail)
    monkeypatch.setattr(embeddings, "embed_batch", _fail)


@pytest.fixture
def fake_ollama(monkeypatch) -> None:
    """Simulate a working Ollama with a deterministic fake embedder."""
    monkeypatch.setattr(embeddings, "is_available", lambda force=False: True)
    monkeypatch.setattr(embeddings, "embed", lambda text: fake_vec(text))
    monkeypatch.setattr(
        embeddings, "embed_batch", lambda texts: [fake_vec(t) for t in texts]
    )
