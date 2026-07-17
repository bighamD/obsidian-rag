from __future__ import annotations

from dataclasses import dataclass

from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult


SearchLikeResult = SearchResult | RankedSearchResult


@dataclass(frozen=True)
class RerankItem:
    """一个候选在召回排序与模型重排中的对应关系。"""

    result: SearchLikeResult
    retrieval_rank: int
    retrieval_score: float
    rerank_rank: int
    rerank_score: float | None
    scoring_text: str


@dataclass(frozen=True)
class RerankRunSummary:
    """一次 Reranker 调用的运行事实，不包含隐藏推理。"""

    enabled: bool
    provider: str
    model: str | None
    device: str | None
    candidate_count: int
    output_count: int
    latency_ms: int
    fallback: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True)
class RerankOutcome:
    """重排结果与本次运行摘要。"""

    items: list[RerankItem]
    summary: RerankRunSummary

    @property
    def results(self) -> list[SearchLikeResult]:
        return [item.result for item in self.items]
