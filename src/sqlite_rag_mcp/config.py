"""Environment-driven configuration.

All settings are read lazily from environment variables so that tests (and
long-running hosts) can change them at any time without re-importing modules.
"""
from __future__ import annotations

import os
from pathlib import Path


def _default_db_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", "").strip() or str(
        Path.home() / ".local" / "share"
    )
    return Path(data_home) / "sqlite-rag-mcp" / "index.db"


class Settings:
    """Lazy view over environment variables (each access re-reads the env)."""

    @property
    def db_path(self) -> Path:
        raw = os.environ.get("SQLITE_RAG_DB", "").strip()
        return Path(raw).expanduser() if raw else _default_db_path()

    @property
    def ollama_host(self) -> str:
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @property
    def embed_model(self) -> str:
        return os.environ.get("SQLITE_RAG_EMBED_MODEL", "nomic-embed-text")

    @property
    def embed_dim(self) -> int:
        return int(os.environ.get("SQLITE_RAG_EMBED_DIM", "768"))

    @property
    def chunk_size_tokens(self) -> int:
        return int(os.environ.get("SQLITE_RAG_CHUNK_TOKENS", "800"))

    @property
    def chunk_overlap_tokens(self) -> int:
        return int(os.environ.get("SQLITE_RAG_CHUNK_OVERLAP", "100"))


settings = Settings()
