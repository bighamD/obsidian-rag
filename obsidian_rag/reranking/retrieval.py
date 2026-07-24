from __future__ import annotations

from dataclasses import asdict, replace

from obsidian_rag.config import RagConfig
from obsidian_rag.reranking.models import RerankOutcome, SearchLikeResult
from obsidian_rag.reranking.service import RerankingService
from obsidian_rag.schema import SearchResult, TextChunk


class RerankingRetrievalService:
    """扩大共享检索候选，在 Parent 去重后统一重排并最终截断。"""

    def __init__(self, retrieval_service, reranking_service: RerankingService, config: RagConfig):
        self.retrieval_service = retrieval_service
        self.reranking_service = reranking_service
        self.config = config

    def search(self, query: str, top_k: int = 5, mode="hybrid", filters=None, collection: str | None = None):
        return self.search_with_outcome(
            query,
            top_k=top_k,
            mode=mode,
            filters=filters,
            collection=collection,
        ).results

    def search_with_outcome(
        self,
        query: str,
        *,
        top_k: int = 5,
        mode="hybrid",
        filters=None,
        collection: str | None = None,
    ) -> RerankOutcome:
        candidate_k = max(top_k, self.config.rerank_candidates)
        candidates = list(
            self.retrieval_service.search(
                query,
                top_k=candidate_k,
                mode=mode,
                filters=filters,
                collection=collection,
            )
        )
        output_k = min(top_k, self.config.rerank_top_k)
        outcome = self.reranking_service.rerank(query, candidates, top_k=output_k)
        summary = asdict(outcome.summary)
        items = [replace(item, result=_with_run_summary(item.result, summary)) for item in outcome.items]
        return replace(outcome, items=items)

    def search_collections(
        self,
        query: str,
        collections: list[str],
        *,
        top_k: int = 5,
        mode="hybrid",
        filters=None,
    ) -> tuple[RerankOutcome, dict[str, str]]:
        results_by_collection: dict[str, list[SearchLikeResult]] = {}
        errors: dict[str, str] = {}
        candidate_k = max(top_k, self.config.rerank_candidates)
        for collection in collections:
            try:
                results_by_collection[collection] = list(
                    self.retrieval_service.search(
                        query,
                        top_k=candidate_k,
                        mode=mode,
                        filters=filters,
                        collection=collection,
                    )
                )
            except Exception as exc:
                errors[collection] = (str(exc).strip() or type(exc).__name__)[:300]
        fused = _cross_collection_candidates(results_by_collection, candidate_k)
        outcome = self.reranking_service.rerank(
            query,
            fused,
            top_k=min(top_k, self.config.rerank_top_k),
        )
        summary = asdict(outcome.summary)
        items = [replace(item, result=_with_run_summary(item.result, summary)) for item in outcome.items]
        return replace(outcome, items=items), errors

    def collection_name(self, collection: str | None = None) -> str:
        return self.retrieval_service.collection_name(collection)


def _cross_collection_candidates(
    results_by_collection: dict[str, list[SearchLikeResult]],
    top_k: int,
    rank_constant: int = 60,
) -> list[SearchLikeResult]:
    fused: list[SearchResult] = []
    for collection, results in results_by_collection.items():
        for rank, result in enumerate(results, start=1):
            metadata = {
                **result.chunk.metadata,
                "collection": collection,
                "collection_rank": rank,
                "collection_score": float(result.score),
                "cross_collection_score": 1 / (rank_constant + rank),
            }
            fused.append(
                SearchResult(
                    chunk=TextChunk(text=result.chunk.text, metadata=metadata),
                    score=metadata["cross_collection_score"],
                )
            )
    fused.sort(key=lambda result: (-result.score, str(result.chunk.metadata.get("collection", ""))))
    return fused[:top_k]


def _with_run_summary(result: SearchLikeResult, summary: dict) -> SearchLikeResult:
    metadata = {**result.chunk.metadata, "rerank_run": summary}
    return replace(result, chunk=TextChunk(text=result.chunk.text, metadata=metadata))
