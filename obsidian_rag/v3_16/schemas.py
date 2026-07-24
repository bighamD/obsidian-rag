from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.core.sandbox import ArtifactRecord, SandboxRuntimeStatus
from obsidian_rag.core.schemas import AgentAskResponse, AgentNodeTiming
from obsidian_rag.v1.schemas import SearchFilters, SearchHit, SearchMode
from obsidian_rag.v3_10.schemas import RunRecord
from obsidian_rag.v3_15.schemas import ApprovalRecord


DeepAgentRunStatus = Literal["waiting_for_approval", "succeeded"]
DeepAgentToolStatus = Literal["requested", "waiting_for_approval", "success", "failed", "rejected"]
DeepAgentMessageRole = Literal["user", "assistant", "tool", "system", "other"]
DeepAgentEventType = Literal[
    "node_started",
    "node_finished",
    "model_completed",
    "tool_requested",
    "tool_completed",
    "approval_requested",
    "approval_resumed",
    "answer_completed",
]


class DeepAgentAskRequest(BaseModel):
    """V3.16 Deep Agent 输入，只保留 Tool Loop 本轮真正使用的参数。

    V3.16 的 Checkpointer 只服务单次 Run 的 HITL 恢复；`conversation_id` 仅用于
    Run 分组，不会把历史 Turn 自动放进 messages。持久多轮 Memory 进入 V3.17。
    """

    question: str = Field(min_length=1, description="当前用户问题，也是初始 HumanMessage 的正文。")
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="前端会话标识；本版用于 Run/审批关联，不代表已启用持久多轮 Memory。",
    )
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="显式限定的知识库 Collection；为空时由模型在 search_notes 参数中选择。",
    )
    top_k: int = Field(default=5, ge=1, le=10, description="search_notes 每次最多返回的知识库 chunks 数。")
    mode: SearchMode = Field(default="hybrid", description="检索模式：dense、keyword 或 hybrid。")
    filters: SearchFilters | None = Field(default=None, description="可选知识库元数据过滤条件。")
    max_iterations: int = Field(
        default=12,
        ge=4,
        le=30,
        description="DeepAgents Graph 的最大递归迭代预算，防止模型无限循环调用工具。",
    )


class DeepAgentToolCall(BaseModel):
    """一条可观察的模型 Tool Call，不包含模型隐藏推理。"""

    sequence: int = Field(ge=1, description="Tool Call 在当前 messages 历史中的顺序。")
    model_call_index: int = Field(ge=1, description="生成该 Tool Call 的第几次模型调用。")
    call_id: str = Field(description="LangChain Tool Call ID，用于匹配后续 ToolMessage 和审批步骤。")
    name: str = Field(description="模型选择的工具名，例如 search_notes 或 write_file。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="模型在看到当前 messages 后生成的工具参数。")
    status: DeepAgentToolStatus = Field(description="该调用当前处于请求、待审批、成功、失败或拒绝状态。")


class DeepAgentToolMessage(BaseModel):
    """工具执行结果进入下一次模型调用前的结构化 ToolMessage 投影。"""

    sequence: int = Field(ge=1, description="ToolMessage 在当前 messages 历史中的顺序。")
    message_id: str | None = Field(default=None, description="LangChain ToolMessage ID。")
    tool_call_id: str = Field(description="被该结果响应的 Tool Call ID。")
    tool_name: str = Field(description="产生该结果的工具名。")
    status: Literal["success", "failed", "rejected"] = Field(description="工具结果状态。")
    content: Any = Field(description="真正进入下一次模型调用的 ToolMessage 内容；search_notes 为结构化 JSON。")
    summary: str = Field(description="供 Swagger 和 Console 快速浏览的非推理摘要。")


class DeepAgentMessage(BaseModel):
    """Checkpoint 中 messages 的安全投影，用于学习 Tool Loop 数据流。"""

    sequence: int = Field(ge=1, description="消息在 Agent messages 中的顺序。")
    message_id: str | None = Field(default=None, description="LangChain 消息 ID；供应商未返回时可能为空。")
    role: DeepAgentMessageRole = Field(description="消息角色：user、assistant、tool、system 或 other。")
    content: Any = Field(description="可见消息正文或结构化内容块，不包含隐藏 chain-of-thought。")
    tool_calls: list[DeepAgentToolCall] = Field(
        default_factory=list,
        description="assistant 消息中请求的工具；其他角色通常为空。",
    )
    tool_call_id: str | None = Field(default=None, description="tool 消息所响应的 Tool Call ID。")
    tool_name: str | None = Field(default=None, description="tool 消息对应的工具名。")


class DeepAgentExecutionEvent(BaseModel):
    """DeepAgents/LangGraph 公开运行事实，不记录模型思维链。"""

    sequence: int = Field(ge=1, description="事件在当前 Run 中的全局顺序。")
    event_type: DeepAgentEventType = Field(description="模型、节点、工具、审批或答案的可观察事件类型。")
    node_name: str | None = Field(default=None, description="对应的 LangGraph/DeepAgents 节点名。")
    status: str = Field(description="事件状态，例如 running、completed、waiting 或 failed。")
    detail: str = Field(description="面向调试的简短事实说明。")
    occurred_at: str = Field(description="事件发生的 UTC ISO 8601 时间。")
    duration_ms: int | None = Field(default=None, ge=0, description="节点完成事件的墙钟耗时。")
    tool_name: str | None = Field(default=None, description="工具相关事件的工具名。")
    tool_call_id: str | None = Field(default=None, description="工具相关事件的 Tool Call ID。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="不含 Secret 和隐藏推理的附加观察数据。")


class DeepAgentArtifact(ArtifactRecord):
    """Core Artifact 元数据及可直接供前端使用的下载地址。"""

    download_url: str = Field(description="按 artifact_id 下载文件的 V3.16 API 地址。")


class DeepAgentNativeResponse(BaseModel):
    """V3.16 原生响应，直接解释 DeepAgents messages/tool loop。"""

    run_id: str = Field(description="当前 Deep Agent Run，同时也是 LangGraph thread_id 和 Workspace ID。")
    status: DeepAgentRunStatus = Field(description="Graph 当前等待审批或已经成功结束。")
    question: str = Field(description="首条 HumanMessage 的原始问题。")
    model_call_count: int = Field(ge=0, description="Checkpoint messages 中完整 AIMessage 的数量。")
    messages: list[DeepAgentMessage] = Field(description="当前 Checkpoint 的 messages 安全投影。")
    tool_calls: list[DeepAgentToolCall] = Field(description="按因果顺序提取的全部 Tool Calls。")
    tool_messages: list[DeepAgentToolMessage] = Field(description="已进入 messages 的全部 Tool Observations。")
    execution_events: list[DeepAgentExecutionEvent] = Field(description="本 Run 的节点、模型、工具和审批事件。")
    graph_path: list[str] = Field(description="按实际执行顺序记录的 DeepAgents/LangGraph 节点名称。")
    node_timings: list[AgentNodeTiming] = Field(description="tasks stream 计算出的逐节点墙钟耗时。")
    final_answer: str = Field(description="最后一条无 tool_calls 的可见 AIMessage；等待审批时为状态说明。")
    selected_collections: list[str] = Field(description="search_notes 实际使用过的知识库 Collections。")
    search_results: list[SearchHit] = Field(description="从 search_notes ToolMessage 解析出的知识库 chunks。")
    artifacts: list[DeepAgentArtifact] = Field(description="当前 Run Workspace 已登记的可下载文件。")


class DeepAgentAskResponse(BaseModel):
    """V3.16 JSON/SSE 统一终态，兼容旧 Console 并增加 DeepAgents 原生观察面。"""

    run: RunRecord = Field(description="持久 Run 生命周期、总耗时、错误与工具摘要。")
    agent_response: AgentAskResponse | None = Field(
        default=None,
        description="为共享 Console 构造的兼容投影；Memory 字段会明确标记本版未写入持久多轮记忆。",
    )
    deep_agent_response: DeepAgentNativeResponse | None = Field(
        default=None,
        description="DeepAgents 原生 messages、Tool Calls、ToolMessages、事件和 Artifact。",
    )
    approval: ApprovalRecord | None = Field(
        default=None,
        description="write_file/edit_file 被 interrupt_on 暂停时的持久审批记录。",
    )


class DeepAgentExecutionResult(BaseModel):
    """Agent Adapter 交给 Runtime 的内部执行结果。"""

    status: DeepAgentRunStatus = Field(description="本次 Graph stream 的终态。")
    compatibility_response: AgentAskResponse = Field(description="共享 Console 使用的兼容 Agent 响应。")
    native_response: DeepAgentNativeResponse = Field(description="V3.16 原生 DeepAgents 响应。")
    approval: ApprovalRecord | None = Field(default=None, description="等待或完成的审批记录。")


class DeepAgentRuntimeConfigResponse(BaseModel):
    """Swagger 可查看的 V3.16 框架、工具、HITL 与 Artifact 配置。"""

    version: Literal["v3.16"] = Field(description="当前学习版本。")
    framework: str = Field(description="当前 Agent Harness 框架与版本。")
    model_adapter: str = Field(description="LLM Provider Adapter。")
    checkpointer_backend: str = Field(description="HITL 恢复使用的 LangGraph Checkpointer。")
    runtime_store_backend: str = Field(description="Run、审批、请求快照和原生响应的持久化实现。")
    tools: list[str] = Field(description="本版重点开放的业务和文件工具。")
    interrupt_tools: list[str] = Field(description="调用前必须人工审批的工具。")
    conversation_memory_enabled: bool = Field(description="是否已把历史对话自动装入当前 messages。")
    json_endpoint: str = Field(description="同步 JSON ask 路径。")
    stream_endpoint: str = Field(description="SSE ask 路径。")
    resume_endpoint: str = Field(description="审批后同步恢复路径模板。")
    resume_stream_endpoint: str = Field(description="审批后 SSE 恢复路径模板。")
    artifact_endpoint: str = Field(description="Artifact 下载路径模板。")
    sandbox: SandboxRuntimeStatus = Field(description="复用的 Core Sandbox Runtime 状态与资源 Profile。")


class DeepAgentHealthResponse(BaseModel):
    """V3.16 API、Checkpoint、Store 和 Workspace 后端健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="关键持久层可用时为 ok。")
    version: Literal["v3.16"] = Field(description="当前学习版本。")
    checkpoint_ready: bool = Field(description="LangGraph PostgreSQL Checkpointer 是否可读取。")
    runtime_store_ready: bool = Field(description="V3.16 PostgreSQL 扩展表是否已初始化。")
    sandbox_available: bool = Field(description="Docker Sandbox 是否可用；纯文件 Backend 仍受 Workspace/路径边界保护。")


class DeepAgentArtifactListResponse(BaseModel):
    """按 Run 查询 DeepAgents Workspace 产物。"""

    run_id: str = Field(description="Artifact 所属 Deep Agent Run。")
    artifacts: list[DeepAgentArtifact] = Field(description="当前 Workspace 中全部可下载文件。")
