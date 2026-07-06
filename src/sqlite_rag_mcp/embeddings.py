"""Local embeddings via Ollama, with graceful unavailability handling.

If the Ollama daemon is not running, nothing breaks: :func:`is_available`
returns ``False`` and callers (indexer/search) degrade to lexical-only mode
with an explicit warning.
"""
from __future__ import annotations

import logging

from sqlite_rag_mcp.config import settings
from sqlite_rag_mcp.retry import retry

log = logging.getLogger(__name__)

_PROBE_TIMEOUT_S = 2.0

# Cached availability probe (None = not probed yet in this process).
_available: bool | None = None


class EmbeddingUnavailableError(RuntimeError):
    """Raised when embeddings cannot be produced (e.g. Ollama is down)."""


def is_available(force: bool = False) -> bool:
    """Return True if the Ollama daemon answers at the configured host.

    The result is cached per process; pass ``force=True`` to re-probe.
    """
    global _available
    if _available is None or force:
        try:
            import ollama

            client = ollama.Client(host=settings.ollama_host, timeout=_PROBE_TIMEOUT_S)
            client.list()
            _available = True
        except Exception as exc:
            log.warning(
                "Ollama not reachable at %s (%s); semantic search disabled",
                settings.ollama_host,
                exc,
            )
            _available = False
    return _available


@retry(max_attempts=3, base_delay=1.0)
def _embed_request(texts: list[str]) -> list[list[float]]:
    import ollama

    client = ollama.Client(host=settings.ollama_host)
    resp = client.embed(model=settings.embed_model, input=texts)
    return [list(vec) for vec in resp["embeddings"]]


def embed(text: str) -> list[float]:
    """Embed a single text. Raises :class:`EmbeddingUnavailableError` on failure."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Raises :class:`EmbeddingUnavailableError` on failure."""
    if not texts:
        return []
    try:
        return _embed_request(texts)
    except Exception as exc:
        raise EmbeddingUnavailableError(
            f"could not embed with model '{settings.embed_model}' "
            f"at {settings.ollama_host}: {exc}"
        ) from exc
