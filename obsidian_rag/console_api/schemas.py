from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from obsidian_rag.core.schemas import MemorySnapshot


class ConsoleFeatures(BaseModel):
    """当前 Console contract 支持的用户可见能力。"""

    model_config = ConfigDict(populate_by_name=True)

    json_api: bool = Field(alias="json", description="是否支持同步 JSON Agent 请求。")
    sse: bool = Field(description="是否支持 SSE Agent 请求。")
    answer_delta: bool = Field(description="是否支持最终答案文本增量事件。")
    reasoning_delta: bool = Field(description="当前是否启用学习调试 reasoning 增量事件。")
    conversation_memory: bool = Field(description="是否支持持久化会话 Memory 读取。")
    conversation_management: bool = Field(description="是否支持服务端会话列表和级联删除。")
    collections: bool = Field(description="Agent 请求是否支持指定知识库 collection。")
    mcp_tools: bool = Field(default=False, description="是否支持 MCP Runtime、Tool Catalog 和 Tool Observation 展示。")
    collection_routing: bool = Field(
        default=False,
        description="是否提供 Knowledge Base Catalog、Planner Collection Selection 和多库检索展示。",
    )
    permission_policy: bool = Field(default=False, description="是否返回逐步骤 allow/confirm/deny 权限报告。")
    skills: bool = Field(default=False, description="是否支持 Core Skill Router、Skill 选择与加载摘要展示。")
    sandbox: bool = Field(default=False, description="是否支持 Docker Sandbox、受控命令和 Artifacts 展示。")


class ConsoleEndpoints(BaseModel):
    """Agent Console 在当前契约下使用的稳定 API 路径。"""

    ask: str = Field(description="同步 JSON Agent 请求路径。")
    stream: str = Field(description="SSE Agent 请求路径。")
    conversations: str = Field(description="会话列表集合路径。")
    conversation: str = Field(description="按 conversation_id 读取会话快照的路径模板。")
    runs: str = Field(description="读取近期 Run 的路径。")
    mcp_runtime: str | None = Field(default=None, description="MCP Server 连接与 Tool Catalog 状态路径。")
    collection_runtime: str | None = Field(default=None, description="Knowledge Base Registry 状态路径。")
    skills_runtime: str | None = Field(default=None, description="Core Skill Registry 状态路径。")
    sandbox_runtime: str | None = Field(default=None, description="Sandbox Backend 与资源限制状态路径。")
    sandbox_artifacts: str | None = Field(default=None, description="按 run_id 查询 Sandbox Artifacts 的路径模板。")


class ConsoleConfigResponse(BaseModel):
    """Agent Console 启动时执行能力协商的稳定响应。"""

    contract_version: Literal["console.v1"] = Field(description="前后端共享的 Console API 契约版本。")
    backend_version: str = Field(description="当前提供契约的学习版后端，仅用于展示和诊断。")
    features: ConsoleFeatures = Field(description="当前后端实际启用的 Console 能力。")
    endpoints: ConsoleEndpoints = Field(description="Console 使用的稳定 API 路径。")
    default_memory_window: int = Field(ge=0, le=20, description="新会话默认读取的最近原始 Turn 数。")


class ConsoleConversationResponse(BaseModel):
    """Agent Console 切换会话时读取的公共 Core Memory 快照。"""

    conversation_id: str = Field(description="浏览器当前选择的会话标识。")
    memory_snapshot: MemorySnapshot = Field(description="从 MySQL 读取的 Core 会话记忆快照。")


class ConsoleConversationSummary(BaseModel):
    """左侧会话历史列表展示的一条服务端持久化会话摘要。"""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str = Field(description="持久化会话唯一标识。")
    title: str = Field(description="由第一条用户问题生成的会话标题。")
    turn_count: int = Field(ge=0, description="当前会话已持久化的原始 Turn 数。")
    created_at: str = Field(description="会话首次写入时间，使用当前 Memory Store 时间格式。")
    updated_at: str = Field(description="会话最近一次写入或摘要更新时间。")


class ConsoleConversationListResponse(BaseModel):
    """Agent Console 从服务端加载的会话历史列表。"""

    conversations: list[ConsoleConversationSummary] = Field(description="按 updated_at 倒序排列的会话摘要。")


class ConsoleConversationDeleteResponse(BaseModel):
    """硬删除 Conversation 及其关联 Turns 后的结果。"""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str = Field(description="被请求删除的会话标识。")
    deleted: bool = Field(description="Conversation 是否实际存在并已删除。")
    deleted_turn_count: int = Field(ge=0, description="随 Conversation 一并删除的关联 Turn 数。")
