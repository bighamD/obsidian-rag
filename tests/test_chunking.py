from obsidian_rag.chunking import chunk_document
from obsidian_rag.schema import SourceDocument


def test_chunk_document_keeps_source_metadata_and_heading_context():
    document = SourceDocument(
        text="# Agent Memory\n\nAlpha beta gamma.\n\n## Retrieval\n\nDelta epsilon zeta.",
        metadata={"source": "agent.md", "title": "Agent Memory", "tags": ["agent"]},
    )

    chunks = chunk_document(document, max_chars=45, overlap_chars=5)

    assert len(chunks) >= 2
    assert chunks[0].text.startswith("# Agent Memory")
    assert chunks[0].metadata["source"] == "agent.md"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["tags"] == ["agent"]


def test_chunk_document_rejects_overlap_larger_than_chunk_size():
    document = SourceDocument(text="abc", metadata={"source": "a.md"})

    try:
        chunk_document(document, max_chars=10, overlap_chars=10)
    except ValueError as exc:
        assert "overlap_chars" in str(exc)
    else:
        raise AssertionError("expected ValueError")
