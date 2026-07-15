from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.v1.schemas import SearchHit, SearchMode


CollectionRoutingStatus = Literal[
    "explicit",
    "disabled",
    "selected",
    "multi_selected",
    "no_collection",
    "invalid_selection",
    "router_error",
]


class KnowledgeBaseManifest(BaseModel):
    """Registry 中一个可路由知识库的轻量元数据。"""

    id: str = Field(
        pattern=COLLECTION_NAME_PATTERN,
        description="知识库稳定 ID，供 Router 选择；不要求与物理 collection 同名。",
    )
    collection: str = Field(
        pattern=COLLECTION_NAME_PATTERN,
        description="实际 Qdrant collection 和 keyword index 命名空间。",
    )
    description: str = Field(min_length=1, description="知识库领域描述，会提供给 LLM Collection Router。")
    triggers: list[str] = Field(default_factory=list, description="帮助 Router 判断适用范围的关键词或示例。")
    enabled: bool = Field(default=True, description="是否允许该知识库成为 Router candidate。")


class KnowledgeBaseListResponse(BaseModel):
    """Registry 列表响应。"""

    registry_path: str = Field(description="当前加载的 Registry YAML 路径。")
    knowledge_bases: list[KnowledgeBaseManifest] = Field(description="已加载的知识库元数据。")
    errors: list[str] = Field(default_factory=list, description="被跳过的无效配置及原因。")


class CollectionRouteRequest(BaseModel):
    """Collection Router 输入；显式 collection 的优先级最高。"""

    question: str = Field(min_length=1, description="用于选择知识库范围的原始用户问题。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="显式指定的物理 collection；提供后跳过 LLM Router。",
    )
    router_enabled: bool = Field(default=True, description="未显式指定 collection 时是否调用 LLM Router。")
    max_collections: int = Field(default=2, ge=1, le=3, description="LLM 最多可以选择的知识库数量。")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"question": "做鸡肉时怎样保证安全？", "router_enabled": True, "max_collections": 2},
                {"question": "番茄炒蛋怎么做？", "collection": "recipes"},
            ]
        }
    }


class CollectionSearchRequest(CollectionRouteRequest):
    """Collection Router + Retrieval 的 JSON 输入。"""

    top_k: int = Field(default=5, ge=1, le=20, description="跨库 RRF 后最终返回的结果数量。")
    mode: SearchMode = Field(default="hybrid", description="每个 collection 内部使用的检索模式。")


class CollectionSelection(BaseModel):
    """Collection Router 的结构化选择，不包含模型隐藏推理。"""

    status: CollectionRoutingStatus = Field(description="显式、单库、多库、无匹配或错误等选择状态。")
    selected_ids: list[str] = Field(default_factory=list, description="最终选择的 Registry 知识库 ID。")
    selected_collections: list[str] = Field(default_factory=list, description="最终允许访问的物理 collection。")
    reason: str = Field(description="面向调试的简短选择原因，不是 chain-of-thought。")
    confidence: float | None = Field(default=None, ge=0, le=1, description="LLM Router 置信度；非 LLM 分支可为 null。")
    candidate_ids: list[str] = Field(default_factory=list, description="本次 Router 实际看到的启用知识库 ID。")


class CollectionTraceEvent(BaseModel):
    """V3.11.3 可观察路由和检索事件。"""

    node_name: str = Field(description="事件所在节点，例如 load_registry、collection_router 或 cross_collection_rrf。")
    event_type: str = Field(description="事件类型，例如 candidates、explicit、selected、retrieved 或 fused。")
    reason: str = Field(description="可观察的执行说明，不包含隐藏推理。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="候选、数量或错误等调试元数据。")


class CollectionRouteResponse(BaseModel):
    """只执行 Collection Router、不访问向量库的响应。"""

    question: str = Field(description="原始用户问题。")
    selection: CollectionSelection = Field(description="最终知识库范围选择。")
    trace: list[CollectionTraceEvent] = Field(description="Registry 与 Router 的真实执行轨迹。")


class CollectionSearchHit(SearchHit):
    """带 collection 范围和第二层 RRF 信息的统一检索结果。"""

    collection: str = Field(description="该结果实际来源的物理 collection。")
    collection_rank: int = Field(ge=1, description="该结果在所属 collection 内的排名。")
    cross_collection_score: float = Field(description="第二层跨 collection RRF 分数。")


class CollectionSearchResponse(BaseModel):
    """路由、每库检索和跨库融合的完整 JSON 响应。"""

    query: str = Field(description="实际执行检索的用户问题。")
    mode: SearchMode = Field(description="每个 collection 内使用的检索模式。")
    selection: CollectionSelection = Field(description="本次实际检索范围。")
    collection_result_counts: dict[str, int] = Field(description="每个成功 collection 的候选结果数量。")
    collection_errors: dict[str, str] = Field(description="单库检索失败摘要；成功时为空对象。")
    results: list[CollectionSearchHit] = Field(description="跨 collection RRF 后的全局 top-k。")
    trace: list[CollectionTraceEvent] = Field(description="Registry、Router、Retrieval 和 Fusion 执行轨迹。")
