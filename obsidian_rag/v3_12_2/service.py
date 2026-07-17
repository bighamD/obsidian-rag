from __future__ import annotations

from dataclasses import asdict

from obsidian_rag.config import RagConfig
from obsidian_rag.reranking.retrieval import RerankingRetrievalService
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_2.evaluation import mean_metrics, ranking_metrics
from obsidian_rag.v3_12_2.schemas import (
    RankingMetrics,
    RerankAskRequest,
    RerankEvalRequest,
    RerankEvalResponse,
    RerankHitView,
    RerankRunView,
    RerankRuntimeConfigResponse,
    RerankSearchRequest,
    RerankSearchResponse,
)


class RerankerLearningService:
    """V3.12.2 教学编排：独立重排、评估和 Agent JSON/SSE。"""

    def __init__(
        self,
        config: RagConfig,
        retrieval: RerankingRetrievalService,
        runtime: StreamingAgentRuntimeService | None = None,
    ):
        self.config = config
        self.retrieval = retrieval
        self.runtime = runtime

    def search(self, request: RerankSearchRequest) -> RerankSearchResponse:
        if request.collections:
            outcome, errors = self.retrieval.search_collections(
                request.query,
                request.collections,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
            )
            collections = request.collections
        else:
            outcome = self.retrieval.search_with_outcome(
                request.query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
                collection=request.collection,
            )
            errors = {}
            collections = [self.retrieval.collection_name(request.collection)]
        return RerankSearchResponse(
            query=request.query,
            collections=collections,
            errors=errors,
            run=RerankRunView(**asdict(outcome.summary)),
            results=[_hit(item) for item in outcome.items],
        )

    def evaluate(self, request: RerankEvalRequest) -> RerankEvalResponse:
        baseline_metrics = []
        reranked_metrics = []
        details = []
        fallback_count = 0
        total_latency = 0
        for case in request.cases:
            candidate_k = max(request.top_k, self.config.rerank_candidates)
            base_results = list(
                self.retrieval.retrieval_service.search(
                    case.query,
                    top_k=candidate_k,
                    mode=request.mode,
                    collection=case.collection,
                )
            )
            outcome = self.retrieval.reranking_service.rerank(case.query, base_results, top_k=request.top_k)
            baseline_ids = [_result_id(result) for result in base_results]
            reranked_ids = [_result_id(item.result) for item in outcome.items]
            relevant = set(case.relevant_ids)
            baseline_metrics.append(ranking_metrics(baseline_ids, relevant, request.top_k))
            reranked_metrics.append(ranking_metrics(reranked_ids, relevant, request.top_k))
            fallback_count += int(outcome.summary.fallback)
            total_latency += outcome.summary.latency_ms
            details.append(
                {
                    "query": case.query,
                    "baseline_ids": baseline_ids[: request.top_k],
                    "reranked_ids": reranked_ids,
                    "relevant_ids": case.relevant_ids,
                    "recall_failed": not any(item in relevant for item in baseline_ids),
                    "fallback": outcome.summary.fallback,
                }
            )
        return RerankEvalResponse(
            case_count=len(request.cases),
            baseline=RankingMetrics(**mean_metrics(baseline_metrics)),
            reranked=RankingMetrics(**mean_metrics(reranked_metrics)),
            fallback_count=fallback_count,
            average_latency_ms=total_latency / len(request.cases),
            details=details,
        )

    def ask(self, request: RerankAskRequest):
        if self.runtime is None:
            raise RuntimeError("Agent runtime is not configured")
        return self.runtime.ask(request)

    def start_stream(self, request: RerankAskRequest) -> str:
        if self.runtime is None:
            raise RuntimeError("Agent runtime is not configured")
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        if self.runtime is None:
            raise RuntimeError("Agent runtime is not configured")
        return self.runtime.stream(run_id)

    def runtime_config(self) -> RerankRuntimeConfigResponse:
        return RerankRuntimeConfigResponse(
            version="v3.12.2",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            rerank_endpoint="/rerank/search",
            evaluation_endpoint="/rerank/evaluate",
            rerank_enabled=self.config.rerank_enabled,
            provider=self.config.rerank_provider,
            model=self.config.rerank_model,
            candidates=self.config.rerank_candidates,
            top_k=self.config.rerank_top_k,
            timeout_seconds=self.config.rerank_timeout_seconds,
        )


def _hit(item) -> RerankHitView:
    metadata = item.result.chunk.metadata
    return RerankHitView(
        source=str(metadata.get("source", "unknown")),
        collection=str(metadata["collection"]) if metadata.get("collection") else None,
        chunk_id=str(metadata["chunk_id"]) if metadata.get("chunk_id") else None,
        parent_id=str(metadata["parent_id"]) if metadata.get("parent_id") else None,
        retrieval_rank=item.retrieval_rank,
        retrieval_score=item.retrieval_score,
        rerank_rank=item.rerank_rank,
        rerank_score=item.rerank_score,
        matched_child_text=item.scoring_text,
        returned_parent_text=str(metadata.get("returned_parent_text") or item.result.chunk.text),
        metadata=metadata,
    )


def _result_id(result) -> str:
    metadata = result.chunk.metadata
    return str(metadata.get("parent_id") or metadata.get("chunk_id") or metadata.get("source") or "")
