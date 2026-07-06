from sqlite_rag_mcp import chunker


def test_short_text_is_single_chunk():
    assert chunker.split("hello world") == ["hello world"]


def test_empty_text_yields_no_chunks():
    assert chunker.split("") == []
    assert chunker.split("\n\n\n") == []


def test_long_text_splits_with_overlap():
    paragraphs = [f"Paragraph {i}. " + ("word " * 60).strip() for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = chunker.split(text, chunk_tokens=200, overlap_tokens=25)
    assert len(chunks) > 1
    max_chars = 200 * 4 + 25 * 4 + 200  # size + overlap carry + slack
    assert all(len(c) <= max_chars for c in chunks)
    # Overlap: the tail of chunk N reappears at the head of chunk N+1.
    tail = chunks[0][-40:]
    assert tail in chunks[1]


def test_paragraph_boundaries_respected():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = chunker.split(text, chunk_tokens=800)
    assert chunks == ["First paragraph.\n\nSecond paragraph."]
