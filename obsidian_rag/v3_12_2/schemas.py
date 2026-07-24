from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.v1.schemas import SearchFilters, SearchMode
from obsidian_rag.v3_10.schemas import ProductionAskRequest, ProductionAskResponse


class RerankAskRequest(ProductionAskRequest):
    """V3.12.2 Agent 输入；检索结果会在 ContextBuilder 前执行可选重排。"""


class RerankAskResponse(ProductionAskResponse):
    """V3.12.2 同步回答；重排详情位于命中 chunk 的 metadata。"""


class RerankSearchRequest(BaseModel):
    """独立观察 Recall、RRF、Parent 与 Reranker 的检索请求。"""

    query: str = Field(min_length=1, description="用于召回和重排的查询文本。")
    top_k: int = Field(default=5, ge=1, le=20, description="重排后最终返回候选数量。")
    mode: SearchMode = Field(default="hybrid", description="dense、keyword 或 hybrid 召回模式。")
    filters: SearchFilters | None = Field(default=None, description="可选知识库 metadata 过滤条件。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="单知识库 Collection；与 collections 二选一。",
    )
    collections: list[str] = Field(
        default_factory=list,
        description="需要统一融合和重排的多个 Collection；为空时使用 collection。",
    )

    @model_validator(mode="after")
    def validate_scope(self):
        if self.collection and self.collections:
            raise ValueError("collection 与 collections 不能同时设置")
        return self


class RerankRunView(BaseModel):
    """一次 Reranker 调用的配置、耗时和回退状态。"""

    enabled: bool = Field(description="是否启用真实模型 Provider。")
    provider: str = Field(description="none、fake 或 sentence_transformers。")
    model: str | None = Field(description="实际配置的重排模型。")
    device: str | None = Field(description="模型推理 device。")
    candidate_count: int = Field(description="进入重排阶段的候选数量。")
    output_count: int = Field(description="重排后输出数量。")
    latency_ms: int = Field(description="重排阶段墙钟耗时，单位毫秒。")
    fallback: bool = Field(description="是否因异常或 timeout 回退 RRF 顺序。")
    fallback_reason: str | None = Field(description="安全回退原因；正常运行时为空。")


class RerankHitView(BaseModel):
    """一个候选在检索与重排前后的可观察结果。"""

    source: str = Field(description="候选来源文件。")
    collection: str | None = Field(description="候选所属 Collection。")
    chunk_id: str | None = Field(description="业务 chunk 标识。")
    parent_id: str | None = Field(description="Parent-Child 索引中的 parent 标识。")
    retrieval_rank: int = Field(description="RRF/召回阶段排名。")
    retrieval_score: float = Field(description="RRF/召回阶段分数。")
    rerank_rank: int = Field(description="模型重排后排名。")
    rerank_score: float | None = Field(description="CrossEncoder 相关性分数；baseline 时为空。")
    matched_child_text: str = Field(description="实际用于重排评分的 child 文本。")
    returned_parent_text: str = Field(description="最终交给 ContextBuilder 的 parent 文本。")
    metadata: dict[str, Any] = Field(description="完整调试 metadata。")


class RerankSearchResponse(BaseModel):
    """独立重排接口响应。"""

    query: str = Field(description="实际执行的查询。")
    collections: list[str] = Field(description="本次查询涉及的 Collection。")
    errors: dict[str, str] = Field(default_factory=dict, description="多 Collection 局部失败摘要。")
    run: RerankRunView = Field(description="Reranker 运行摘要。")
    results: list[RerankHitView] = Field(description="按最终 rerank rank 排列的候选。")


class RerankEvalCase(BaseModel):
    """一条离线对照评估题。"""

    query: str = Field(min_length=1, description="评估查询。")
    relevant_ids: list[str] = Field(min_length=1, description="相关 parent_id、chunk_id 或 source 标识。")
    collection: str | None = Field(default=None, pattern=COLLECTION_NAME_PATTERN, description="评估 Collection。")


class RerankEvalRequest(BaseModel):
    """复用同一召回候选比较 baseline 与 Reranker。"""

    cases: list[RerankEvalCase] = Field(min_length=1, description="评估题集合。")
    top_k: int = Field(default=5, ge=1, le=20, description="指标 K 值。")
    mode: SearchMode = Field(default="hybrid", description="固定召回模式。")


class RankingMetrics(BaseModel):
    """一组排序质量指标。"""

    hit_at_k: float = Field(description="至少命中一个相关候选的比例。")
    recall_at_k: float = Field(description="Top K 覆盖相关候选的比例。")
    mrr: float = Field(description="首个相关候选倒数排名。")
    ndcg_at_k: float = Field(description="Top K 归一化折损累计增益。")


class RerankEvalResponse(BaseModel):
    """RRF baseline 与 Reranker 的汇总对照。"""

    case_count: int = Field(description="实际评估题数。")
    baseline: RankingMetrics = Field(description="原始 RRF/召回顺序指标。")
    reranked: RankingMetrics = Field(description="模型重排顺序指标。")
    fallback_count: int = Field(description="发生 fail-open 回退的题数。")
    average_latency_ms: float = Field(description="平均重排耗时。")
    details: list[dict[str, Any]] = Field(description="逐题排名变化和召回失败信息。")


class RerankRuntimeConfigResponse(BaseModel):
    """V3.12.2 端点与 Reranker 配置说明。"""

    version: Literal["v3.12.2"] = Field(description="当前学习版本。")
    json_endpoint: str = Field(description="完整 Agent JSON 接口。")
    stream_endpoint: str = Field(description="Agent SSE 接口。")
    rerank_endpoint: str = Field(description="独立观察重排接口。")
    evaluation_endpoint: str = Field(description="离线对照评估接口。")
    rerank_enabled: bool = Field(description="当前是否开启真实重排。")
    provider: str = Field(description="当前 Reranker Provider。")
    model: str = Field(description="当前模型。")
    candidates: int = Field(description="进入 Reranker 的候选上限。")
    top_k: int = Field(description="Reranker 默认输出上限。")
    timeout_seconds: float = Field(description="调用 timeout 秒数。")


class RerankHealthResponse(BaseModel):
    """V3.12.2 FastAPI 健康响应。"""

    status: Literal["ok"] = Field(description="API 进程健康状态。")
    version: Literal["v3.12.2"] = Field(description="当前学习版本。")
    capability: str = Field(description="当前版本主要学习能力。")
