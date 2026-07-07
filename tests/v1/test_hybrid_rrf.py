from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v1.retrieval.hybrid import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_combines_dense_and_keyword_rankings():
    dense_first = SearchResult(
        chunk=TextChunk(text="dense winner", metadata={"source": "dense.md", "chunk_id": "KB-001"}),
        score=0.9,
    )
    shared = SearchResult(
        chunk=TextChunk(text="shared result", metadata={"source": "shared.md", "chunk_id": "KB-002"}),
        score=0.8,
    )
    keyword_first = SearchResult(
        chunk=TextChunk(text="keyword winner", metadata={"source": "keyword.md", "chunk_id": "KB-003"}),
        score=3.0,
    )

    fused = reciprocal_rank_fusion(
        dense_results=[dense_first, shared],
        keyword_results=[keyword_first, shared],
        top_k=3,
    )

    assert fused[0].chunk.metadata["chunk_id"] == "KB-002"
    assert fused[0].dense_rank == 2
    assert fused[0].keyword_rank == 2
    assert fused[1].dense_rank == 1
    assert fused[1].keyword_rank is None
    assert fused[2].dense_rank is None
    assert fused[2].keyword_rank == 1
