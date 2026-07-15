from __future__ import annotations

from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult


def reciprocal_rank_fusion(
    dense_results: list[SearchResult],
    keyword_results: list[SearchResult],
    top_k: int = 5,
    rank_constant: int = 60,
) -> list[RankedSearchResult]:
    by_key: dict[str, dict[str, object]] = {}

    for rank, result in enumerate(dense_results, start=1):
        item = by_key.setdefault(_result_key(result), {"chunk": result.chunk, "score": 0.0})
        item["score"] = float(item["score"]) + 1 / (rank_constant + rank)
        item["dense_rank"] = rank
        item["dense_score"] = result.score

    for rank, result in enumerate(keyword_results, start=1):
        item = by_key.setdefault(_result_key(result), {"chunk": result.chunk, "score": 0.0})
        item["score"] = float(item["score"]) + 1 / (rank_constant + rank)
        item["keyword_rank"] = rank
        item["keyword_score"] = result.score

    fused = [
        RankedSearchResult(
            chunk=item["chunk"],
            score=float(item["score"]),
            dense_rank=item.get("dense_rank"),
            keyword_rank=item.get("keyword_rank"),
            dense_score=item.get("dense_score"),
            keyword_score=item.get("keyword_score"),
            hybrid_score=float(item["score"]),
        )
        for item in by_key.values()
    ]
    fused.sort(key=lambda result: result.score, reverse=True)
    return fused[:top_k]


def _result_key(result: SearchResult) -> str:
    metadata = result.chunk.metadata
    node_id = metadata.get("node_id")
    if node_id:
        return f"node_id:{node_id}"
    chunk_id = metadata.get("chunk_id")
    if chunk_id:
        return f"chunk_id:{chunk_id}"
    source = metadata.get("source", "")
    chunk_index = metadata.get("chunk_index", "")
    return f"{source}:{chunk_index}:{result.chunk.text[:80]}"
