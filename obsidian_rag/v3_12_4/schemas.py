from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.core.collections.schemas import KnowledgeBaseManifest, RetrievalScope
from obsidian_rag.v3_12_3.schemas import McpAgentAskRequest, McpTransport


class RoutedMcpAskRequest(McpAgentAskRequest):
    """V3.12.4 Agent 输入：在 MCP 控制之外增加知识库范围路由参数。"""

    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="显式指定 Collection；为空时允许 Collection Router 自动选择。",
    )
    collection_router_enabled: bool = Field(
        default=True,
        description="未显式指定 Collection 且 Planner 需要 search 时，是否调用 LLM Collection Router。",
    )
    max_collections: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Collection Router 最多可以选择的知识库数量。",
    )


class CollectionRouteDebugRequest(BaseModel):
    """Swagger 中独立观察 Collection Scope Resolver 的输入。"""

    question: str = Field(min_length=1, description="用于选择知识库范围的原始问题。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="显式 Collection；有值时跳过 LLM Router。",
    )
    collection_router_enabled: bool = Field(default=True, description="是否启用 LLM Collection Router。")
    max_collections: int = Field(default=2, ge=1, le=3, description="最多选择的知识库数量。")


class CollectionRouteDebugResponse(BaseModel):
    """独立 Collection 路由结果，不执行知识库检索。"""

    question: str = Field(description="原始问题。")
    scope: RetrievalScope = Field(description="解析后的知识库访问范围。")


class CollectionRuntimeResponse(BaseModel):
    """Agent Console 和 Swagger 使用的 Knowledge Base Registry 快照。"""

    registry_path: str = Field(description="实际加载的 Registry 路径。")
    knowledge_bases: list[KnowledgeBaseManifest] = Field(description="Registry 中全部有效知识库。")
    enabled_ids: list[str] = Field(description="当前允许 Router 选择的知识库 ID。")
    errors: list[str] = Field(default_factory=list, description="加载时跳过的无效配置摘要。")


class RoutedMcpRuntimeConfigResponse(BaseModel):
    """V3.12.4 Agent、Collection Router、Reranker 和 MCP 能力说明。"""

    version: Literal["v3.12.4"] = Field(description="当前学习版本。")
    json_endpoint: str = Field(description="同步完整 Agent 响应路径。")
    stream_endpoint: str = Field(description="SSE Agent 运行路径。")
    collection_runtime_endpoint: str = Field(description="Knowledge Base Registry 状态路径。")
    collection_route_endpoint: str = Field(description="独立 Collection Router 调试路径。")
    mcp_runtime_endpoint: str = Field(description="MCP Runtime 状态路径。")
    transports: list[McpTransport] = Field(description="支持的 MCP Transports。")
    persistent_mcp_sessions: bool = Field(description="是否跨 Agent 请求复用 MCP Session。")
    collection_routing: bool = Field(description="是否在 search step 前解析知识库范围。")
    multi_collection_reranking: bool = Field(description="是否统一融合并重排多个 Collection 候选。")
    permission_policy_enabled: bool = Field(description="是否已启用下一阶段 Permission Policy。")


class RoutedMcpHealthResponse(BaseModel):
    """V3.12.4 API、MCP 与 Knowledge Base Registry 健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="关键依赖全部正常时为 ok。")
    version: Literal["v3.12.4"] = Field(description="当前学习版本。")
    mcp_started: bool = Field(description="MCP Connection Manager 是否已启动。")
    connected_mcp_servers: int = Field(ge=0, description="当前已连接 MCP Server 数。")
    enabled_knowledge_bases: int = Field(ge=0, description="当前可供 Collection Router 选择的知识库数。")
    registry_error_count: int = Field(ge=0, description="Knowledge Base Registry 加载错误数。")
