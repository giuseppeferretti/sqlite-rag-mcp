"""Paragraph-aware text chunking with overlap."""
from __future__ import annotations

import re

from sqlite_rag_mcp.config import settings

_APPROX_CHARS_PER_TOKEN = 4


def split(
    text: str,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[str]:
    """Split ``text`` into overlapping chunks, respecting paragraph breaks.

    Token counts are approximated as ``chars / 4`` — good enough for sizing
    retrieval chunks without pulling in a tokenizer dependency.
    """
    max_chars = (chunk_tokens or settings.chunk_size_tokens) * _APPROX_CHARS_PER_TOKEN
    overlap_chars = (
        overlap_tokens
        if overlap_tokens is not None
        else settings.chunk_overlap_tokens
    ) * _APPROX_CHARS_PER_TOKEN

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buffer) + len(para) + 2 > max_chars and buffer:
            chunks.append(buffer.strip())
            # Carry the tail of the previous chunk forward as overlap.
            buffer = buffer[-overlap_chars:] + "\n\n" + para if overlap_chars else para
        else:
            buffer = buffer + ("\n\n" if buffer else "") + para

    if buffer.strip():
        chunks.append(buffer.strip())

    return chunks
