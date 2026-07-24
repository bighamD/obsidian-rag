from __future__ import annotations

from obsidian_rag.config import RagConfig, with_collection
from obsidian_rag.parent_retrieval import expand_parent_results
from obsidian_rag.pipeline import search as dense_search
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.hybrid import reciprocal_rank_fusion
from obsidian_rag.v1.retrieval.keyword import KeywordIndex, keyword_index_path
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import SearchFilters, SearchMode


class RetrievalService:
    def __init__(self, config: RagConfig):
        self.config = config

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: SearchMode = "hybrid",
        filters: SearchFilters | None = None,
        collection: str | None = None,
    ) -> list[SearchResult | RankedSearchResult]:
        config = with_collection(self.config, collection)
        if mode == "dense":
            recall_k = max(top_k * 3, top_k)
            raw = self._filter_results(
                dense_search(query, config, top_k=recall_k, expand_parents=False),
                filters,
            )
            return expand_parent_results(raw, top_k)
        if mode == "keyword":
            recall_k = max(top_k * 3, top_k)
            raw = self._keyword_search(query, config=config, top_k=recall_k, filters=filters)
            return expand_parent_results(raw, top_k)
        if mode == "hybrid":
            recall_k = max(top_k * 3, top_k)
            dense_results = self._filter_results(
                dense_search(query, config, top_k=recall_k, expand_parents=False),
                filters,
            )
            keyword_results = self._keyword_search(query, config=config, top_k=recall_k, filters=filters)
            fused = reciprocal_rank_fusion(dense_results, keyword_results, top_k=recall_k)
            return expand_parent_results(fused, top_k)
        raise ValueError(f"Unsupported search mode: {mode}")

    def compare_search(
        self,
        query: str,
        top_k: int = 5,
        filters: SearchFilters | None = None,
        collection: str | None = None,
    ) -> dict[str, list[SearchResult | RankedSearchResult]]:
        dense_results = self.search(query, top_k=top_k, mode="dense", filters=filters, collection=collection)
        keyword_results = self.search(query, top_k=top_k, mode="keyword", filters=filters, collection=collection)
        hybrid_results = self.search(query, top_k=top_k, mode="hybrid", filters=filters, collection=collection)
        return {"dense": dense_results, "keyword": keyword_results, "hybrid": hybrid_results}

    def collection_name(self, collection: str | None = None) -> str:
        """返回本次检索实际使用的 collection，供 API / trace 回显。"""

        return with_collection(self.config, collection).collection_name

    def _keyword_search(
        self,
        query: str,
        config: RagConfig,
        top_k: int,
        filters: SearchFilters | None,
    ) -> list[SearchResult]:
        index = KeywordIndex(keyword_index_path(config.db_path, config.collection_name))
        index.load()
        return self._filter_results(index.search(query, top_k=top_k), filters)[:top_k]

    def _filter_results(
        self,
        results: list[SearchResult],
        filters: SearchFilters | None,
    ) -> list[SearchResult]:
        if filters is None:
            return results
        return [result for result in results if _matches_filters(result, filters)]


def _matches_filters(result: SearchResult, filters: SearchFilters) -> bool:
    metadata = result.chunk.metadata
    source = str(metadata.get("source", ""))
    if filters.path and filters.path not in source:
        return False
    if filters.file_type and not source.endswith(filters.file_type):
        return False
    if filters.tag:
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        if filters.tag not in [str(tag) for tag in tags]:
            return False
    return True
