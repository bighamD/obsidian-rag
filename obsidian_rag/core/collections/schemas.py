from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN


RetrievalScopeStatus = Literal[
    "not_required",
    "explicit",
    "disabled",
    "selected",
    "multi_selected",
    "no_collection",
    "invalid_selection",
    "router_error",
]


class KnowledgeBaseManifest(BaseModel):
    """Registry 中一个允许 Collection Router 选择的知识库。"""

    id: str = Field(pattern=COLLECTION_NAME_PATTERN, description="提供给 Router 的稳定知识库 ID。")
    collection: str = Field(pattern=COLLECTION_NAME_PATTERN, description="实际 Qdrant 和 Keyword Index Collection。")
    description: str = Field(min_length=1, description="知识库领域与内容范围说明。")
    triggers: list[str] = Field(default_factory=list, description="帮助 Router 判断适用范围的关键词或问题示例。")
    enabled: bool = Field(default=True, description="是否允许该知识库进入 Router candidates。")


class RetrievalScopeRequest(BaseModel):
    """Core Agent 在执行 search steps 前交给 Resolver 的稳定输入。"""

    question: str = Field(min_length=1, description="用于确定全局知识库范围的当前用户问题。")
    explicit_collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="请求显式指定的 Collection；有值时跳过 LLM Router。",
    )
    router_enabled: bool = Field(description="未显式指定 Collection 时是否允许调用 Collection Router。")
    max_collections: int = Field(default=2, ge=1, le=3, description="自动路由最多允许选择的知识库数量。")


class RetrievalScope(BaseModel):
    """本轮 Agent search steps 被允许访问的知识库范围。"""

    status: RetrievalScopeStatus = Field(description="未需要、显式、自动选择、无匹配或错误等路由状态。")
    selected_ids: list[str] = Field(default_factory=list, description="最终选择的 Registry 知识库 ID。")
    selected_collections: list[str] = Field(default_factory=list, description="最终允许检索的物理 Collections。")
    candidate_ids: list[str] = Field(default_factory=list, description="Resolver 本次实际看到的启用知识库 ID。")
    reason: str = Field(description="可观察的路由原因摘要，不包含模型隐藏推理。")
    confidence: float | None = Field(default=None, ge=0, le=1, description="LLM Router 置信度；非 LLM 分支为空。")
    registry_path: str | None = Field(default=None, description="实际加载的 Knowledge Base Registry 路径。")
    errors: dict[str, str] = Field(default_factory=dict, description="Registry、Router 或 Collection 检索局部错误。")
