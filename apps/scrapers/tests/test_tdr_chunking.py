from agenteperry.tdr.chunking import chunk_pages
from agenteperry.tdr.models import TdrPage


def test_chunk_pages_preserves_page_and_overlap():
    text = " ".join(f"palabra{i}" for i in range(80))
    chunks = chunk_pages([TdrPage(page_number=3, text_content=text)], max_chars=220, overlap_chars=40)

    assert len(chunks) > 1
    assert all(chunk.page_start == 3 for chunk in chunks)
    assert all(chunk.page_end == 3 for chunk in chunks)
    assert chunks[0].chunk_index == 0
    assert chunks[1].page_start == chunks[0].page_start


def test_chunk_pages_skips_empty_pages():
    chunks = chunk_pages([TdrPage(page_number=1, text_content="   \n\t  ")])

    assert chunks == []


def test_chunk_pages_rejects_invalid_overlap():
    try:
        chunk_pages([TdrPage(page_number=1, text_content="x" * 300)], max_chars=300, overlap_chars=300)
    except ValueError as exc:
        assert "overlap_chars" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
