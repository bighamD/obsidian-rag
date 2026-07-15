from __future__ import annotations

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v1.retrieval.models import RankedSearchResult


def expand_parent_results(
    results: list[SearchResult | RankedSearchResult],
    top_k: int,
) -> list[SearchResult | RankedSearchResult]:
    """按 parent_id 去重，并保留真正命中的 child 作为可观察证据。"""

    expanded: list[SearchResult | RankedSearchResult] = []
    seen: set[str] = set()
    for result in results:
        metadata = dict(result.chunk.metadata)
        parent_id = str(metadata.get("parent_id") or metadata.get("node_id") or "")
        if parent_id and parent_id in seen:
            continue
        if parent_id:
            seen.add(parent_id)
        matched_child = result.chunk.text
        parent_text = str(metadata.get("parent_text") or matched_child)
        metadata["matched_child_text"] = matched_child
        metadata["returned_parent_text"] = parent_text
        expanded_chunk = TextChunk(text=parent_text, metadata=metadata)
        if isinstance(result, RankedSearchResult):
            expanded.append(
                RankedSearchResult(
                    chunk=expanded_chunk,
                    score=result.score,
                    dense_rank=result.dense_rank,
                    keyword_rank=result.keyword_rank,
                    dense_score=result.dense_score,
                    keyword_score=result.keyword_score,
                    hybrid_score=result.hybrid_score,
                )
            )
        else:
            expanded.append(SearchResult(chunk=expanded_chunk, score=result.score))
        if len(expanded) >= top_k:
            break
    return expanded
