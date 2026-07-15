from obsidian_rag.adaptive_chunking import ADAPTIVE_CHUNK_SCHEMA_VERSION, adaptive_parent_child_chunks
from obsidian_rag.docling_ingestion import DoclingBatch, DoclingConversion
from obsidian_rag.parent_retrieval import expand_parent_results
from obsidian_rag.schema import SearchResult, TextChunk


def _raw(text: str, headings: list[str], index: int) -> TextChunk:
    return TextChunk(
        text=text,
        metadata={
            "source": "vueuse.md",
            "chunk_index": index,
            "heading_path": headings,
            "page_numbers": [],
            "raw_chunk_text": text,
        },
    )


def _batch(chunks: list[TextChunk]) -> DoclingBatch:
    markdown = """# VueUse

## VU-001：useOne

```
chunk_id: VU-001
title: useOne
```

### 知识内容

第一个 Hook。

## VU-002：useTwo

### 知识内容

第二个 Hook。
"""
    conversion = DoclingConversion(
        source="vueuse.md",
        title="VueUse",
        status="success",
        page_count=0,
        item_count=len(chunks),
        markdown=markdown,
        document=object(),
    )
    return DoclingBatch(conversions=[conversion], chunks=chunks, errors=[])


def test_adaptive_chunker_merges_small_blocks_under_same_structural_parent():
    chunks = [
        _raw("chunk_id: VU-001", ["VueUse", "VU-001：useOne"], 0),
        _raw("使用场景", ["VueUse", "VU-001：useOne", "使用场景"], 1),
        _raw("第一个 Hook。", ["VueUse", "VU-001：useOne", "知识内容"], 2),
        _raw("chunk_id: VU-002", ["VueUse", "VU-002：useTwo"], 3),
        _raw("第二个 Hook。", ["VueUse", "VU-002：useTwo", "知识内容"], 4),
    ]

    result = adaptive_parent_child_chunks(
        _batch(chunks),
        len,
        parent_tokens=1000,
        child_tokens=400,
        child_overlap=40,
    )

    assert len(result) == 2
    assert result[0].metadata["chunk_id"] == "VU-001"
    assert result[0].metadata["chunk_schema_version"] == ADAPTIVE_CHUNK_SCHEMA_VERSION
    assert "使用场景" in result[0].metadata["parent_text"]
    assert "第一个 Hook" in result[0].metadata["parent_text"]


def test_adaptive_chunker_splits_long_parent_into_children_with_shared_parent_id():
    chunks = [_raw("A" * 900, ["Guide", "Long Section"], 0)]

    result = adaptive_parent_child_chunks(
        _batch(chunks),
        len,
        parent_tokens=700,
        child_tokens=300,
        child_overlap=20,
    )

    assert len(result) > 1
    assert len({chunk.metadata["parent_id"] for chunk in result}) >= 1
    assert all(chunk.metadata["child_token_count"] <= 340 for chunk in result)


def test_parent_expansion_deduplicates_children_and_returns_complete_parent():
    results = [
        SearchResult(
            chunk=TextChunk(
                text=f"matched child {index}",
                metadata={"node_id": f"c{index}", "parent_id": "p1", "parent_text": "complete parent"},
            ),
            score=1.0 - index / 10,
        )
        for index in range(2)
    ]

    expanded = expand_parent_results(results, top_k=5)

    assert len(expanded) == 1
    assert expanded[0].chunk.text == "complete parent"
    assert expanded[0].chunk.metadata["matched_child_text"] == "matched child 0"
