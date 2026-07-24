from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.core.sandbox import SandboxRuntimeStatus
from obsidian_rag.core.schemas import AgentAskResponse
from obsidian_rag.v1.schemas import SearchFilters, SearchMode
from obsidian_rag.v3_10.schemas import RunRecord
from obsidian_rag.v3_15.schemas import ApprovalRecord
from obsidian_rag.v3_16.schemas import DeepAgentNativeResponse


MemoryKind = Literal["preference", "fact", "decision"]
DurableRunStatus = Literal["waiting_for_approval", "succeeded"]


class DurableAgentAskRequest(BaseModel):
    """V3.17 输入：稳定 Conversation scope 与本轮 DeepAgents 参数。"""

    question: str = Field(min_length=1, description="当前用户问题；只作为本轮新增 HumanMessage。")
    tenant_id: str = Field(default="tenant_demo", min_length=1, max_length=120, description="租户隔离标识，由服务端身份层确认。")
    user_id: str = Field(default="user_demo", min_length=1, max_length=120, description="长期 Memory 的用户隔离标识。")
    assistant_id: str = Field(default="obsidian_rag", min_length=1, max_length=120, description="Assistant 隔离标识，不同 Assistant 默认不共享长期 Memory。")
    conversation_id: str | None = Field(default=None, min_length=1, max_length=120, description="稳定会话标识；相同值映射到相同 LangGraph thread_id。")
    collection: str | None = Field(default=None, pattern=COLLECTION_NAME_PATTERN, description="显式限定的知识库 Collection；为空时由 Tool Call 决定。")
    top_k: int = Field(default=5, ge=1, le=10, description="search_notes 每次最多返回的知识库 chunks 数。")
    mode: SearchMode = Field(default="hybrid", description="检索模式：dense、keyword 或 hybrid。")
    filters: SearchFilters | None = Field(default=None, description="可选知识库元数据过滤条件。")
    max_iterations: int = Field(default=12, ge=4, le=30, description="DeepAgents Graph 的最大递归迭代预算。")


class DurableRuntimeContext(BaseModel):
    """只读 Run Context；Store namespace 必须从这里构造。"""

    tenant_id: str = Field(description="经过验证的租户标识。")
    user_id: str = Field(description="经过验证的用户标识。")
    assistant_id: str = Field(description="当前 Assistant 标识。")
    conversation_id: str = Field(description="业务 Conversation 标识。")
    thread_id: str = Field(description="LangGraph Checkpointer 使用的稳定线程标识。")
    run_id: str = Field(description="当前一次执行的唯一 Run 标识。")


class DurableConversation(BaseModel):
    """Conversation Repository 中的业务元数据，不复制完整 Graph messages。"""

    conversation_id: str = Field(description="持久会话唯一标识。")
    thread_id: str = Field(description="该会话稳定映射的 LangGraph thread_id。")
    tenant_id: str = Field(description="Conversation 所属租户。")
    user_id: str = Field(description="Conversation 所属用户。")
    assistant_id: str = Field(description="Conversation 所属 Assistant。")
    title: str = Field(description="由第一条问题生成、可供前端展示的会话标题。")
    status: Literal["active", "deleted"] = Field(description="会话业务状态。")
    turn_count: int = Field(ge=0, description="该会话已接受的新用户请求数量；resume 不重复计数。")
    created_at: str = Field(description="会话创建 UTC 时间。")
    updated_at: str = Field(description="会话最近请求或状态变更 UTC 时间。")


class DurableConversationListResponse(BaseModel):
    """当前 scope 下的 Conversation 列表。"""

    conversations: list[DurableConversation] = Field(description="按 updated_at 倒序排列的会话。")


class DurableConversationDeleteResponse(BaseModel):
    """删除 Conversation 与 Thread Checkpoint 的结果。"""

    conversation_id: str = Field(description="被删除的 Conversation。")
    thread_id: str = Field(description="被清理 Checkpoint 的稳定 Thread。")
    deleted: bool = Field(description="Conversation 是否存在并完成删除。")
    deleted_checkpoint_rows: int = Field(ge=0, description="从 LangGraph Checkpoint 表删除的行数。")
    long_term_memory_preserved: bool = Field(description="是否按默认边界保留用户长期 Memory。")


class LongTermMemoryItem(BaseModel):
    """LangGraph Store 中一条可治理的长期 Memory；不是原始 Turn。"""

    memory_id: str = Field(description="长期 Memory 唯一标识。")
    kind: MemoryKind = Field(description="Memory 类型：偏好、长期事实或已确认决策。")
    content: str = Field(description="允许跨 Conversation 使用的稳定信息。")
    reason: str | None = Field(default=None, description="保存该 Memory 的原因或用户指令摘要。")
    source_run_id: str | None = Field(default=None, description="产生或最近更新该 Memory 的 Run。")
    created_at: str = Field(description="Memory 创建 UTC 时间。")
    updated_at: str = Field(description="Memory 最近更新 UTC 时间。")


class LongTermMemoryPutRequest(BaseModel):
    """创建或更新一条长期 Memory。"""

    memory_id: str | None = Field(default=None, description="为空时创建新 Memory；非空时更新该 ID。")
    kind: MemoryKind = Field(description="长期 Memory 类型。")
    content: str = Field(min_length=1, max_length=2000, description="稳定偏好、长期事实或确认后的决策。")
    reason: str | None = Field(default=None, max_length=500, description="保存原因；不得包含 Secret。")
    tenant_id: str = Field(default="tenant_demo", description="目标租户 scope。")
    user_id: str = Field(default="user_demo", description="目标用户 scope。")
    assistant_id: str = Field(default="obsidian_rag", description="目标 Assistant scope。")


class LongTermMemoryListResponse(BaseModel):
    """一个用户 scope 下的长期 Memory 列表。"""

    namespace: list[str] = Field(description="实际使用的 tenant/assistant/user Store namespace。")
    memories: list[LongTermMemoryItem] = Field(description="按更新时间倒序排列的长期 Memory。")


class LongTermMemoryDeleteResponse(BaseModel):
    """显式删除长期 Memory 的结果。"""

    memory_id: str = Field(description="被请求删除的 Memory ID。")
    deleted: bool = Field(description="该 Memory 是否存在并被删除。")


class MemoryAuditRecord(BaseModel):
    """Memory/Conversation/Summary 生命周期的安全审计记录。"""

    audit_id: str = Field(description="审计记录唯一标识。")
    operation: str = Field(description="create、update、delete、summary 或 checkpoint_cleanup。")
    tenant_id: str = Field(description="审计事件所属租户。")
    user_id: str = Field(description="审计事件所属用户。")
    assistant_id: str = Field(description="审计事件所属 Assistant。")
    conversation_id: str | None = Field(default=None, description="关联 Conversation；纯长期 Memory 操作可为空。")
    run_id: str | None = Field(default=None, description="关联 Run；管理 API 操作可为空。")
    memory_id: str | None = Field(default=None, description="关联长期 Memory ID。")
    actor: str = Field(description="触发操作的 actor，例如 agent、user 或 system。")
    summary: str = Field(description="不含 Secret 和完整敏感内容的操作摘要。")
    created_at: str = Field(description="事件发生 UTC 时间。")


class MemoryAuditListResponse(BaseModel):
    """当前 scope 下的 Memory Audit 列表。"""

    audits: list[MemoryAuditRecord] = Field(description="按 created_at 倒序排列的审计记录。")


class ContextSummarySnapshot(BaseModel):
    """DeepAgents `_summarization_event` 的安全投影。"""

    triggered: bool = Field(description="当前 Thread 是否已经产生 Summary event。")
    cutoff_index: int = Field(ge=0, description="原始 messages 中已被 Summary 覆盖的截止位置。")
    summary_text: str = Field(description="真正用于后续模型调用的 SummaryMessage 可见正文。")
    history_file_path: str | None = Field(default=None, description="被卸载旧历史的 `/context/` Store 路径。")


class DurableContextSnapshot(BaseModel):
    """本次 Run 的 Context 生命周期观察面，不等同于精确 Wire Prompt。"""

    conversation_id: str = Field(description="当前 Conversation。")
    thread_id: str = Field(description="恢复 messages 的稳定 LangGraph Thread。")
    run_id: str = Field(description="生成该快照的一次执行。")
    thread_message_count: int = Field(ge=0, description="Checkpoint 中保留的原始 messages 数；DeepAgents Summary 不会删除原始日志。")
    estimated_message_tokens: int = Field(ge=0, description="对原始 messages 的通用近似 token 估算，不是供应商账单值。")
    model_context_tokens: int = Field(ge=1, description="用于 DeepAgents Summary Profile 的模型输入窗口。")
    summary_trigger_fraction: float = Field(gt=0, le=1, description="DeepAgents 模型 Profile 默认触发比例。")
    summary: ContextSummarySnapshot = Field(description="当前 `_summarization_event` 安全投影。")
    long_term_memories: list[LongTermMemoryItem] = Field(description="本次 Runtime scope 可读取的长期 Memory；实际 Prompt 由 profile.md 注入。")
    memory_profile_path: str = Field(description="MemoryMiddleware 实际读取的 StoreBackend 文件路径。")
    exact_wire_prompt_available: bool = Field(default=False, description="是否能声称该快照就是供应商收到的精确 Prompt；本版固定为 false。")


class DurableDeepAgentNativeResponse(DeepAgentNativeResponse):
    """V3.16 原生 Tool Loop 投影加上 V3.17 Durable Context。"""

    run_id: str = Field(description="当前一次执行的 Run ID，不再等同于 thread_id。")
    thread_id: str = Field(description="当前 Conversation 使用的稳定 LangGraph thread_id。")
    durable_context: DurableContextSnapshot = Field(description="Thread、Summary、长期 Memory 和 Context Profile 观察数据。")


class DurableAgentAskResponse(BaseModel):
    """V3.17 JSON/SSE 统一终态。"""

    run: RunRecord = Field(description="一次执行的 Production Run 生命周期。")
    agent_response: AgentAskResponse | None = Field(default=None, description="共享 Console 使用的兼容 AgentAskResponse 投影。")
    deep_agent_response: DurableDeepAgentNativeResponse | None = Field(default=None, description="DeepAgents 原生 Tool Loop 与 Durable Context。")
    approval: ApprovalRecord | None = Field(default=None, description="写入 Artifact 前的持久审批记录。")


class DurableExecutionResult(BaseModel):
    """V3.17 Agent Adapter 交给 Runtime 的内部结果。"""

    status: DurableRunStatus = Field(description="Graph 等待审批或成功结束。")
    compatibility_response: AgentAskResponse = Field(description="共享 Console 兼容响应。")
    native_response: DurableDeepAgentNativeResponse = Field(description="包含 Durable Context 的原生响应。")
    approval: ApprovalRecord | None = Field(default=None, description="当前审批记录。")


class DurableRuntimeConfigResponse(BaseModel):
    """Swagger 可查看的 V3.17 Memory、Context 和 Backend 配置。"""

    version: Literal["v3.17"] = Field(description="当前学习版本。")
    framework: str = Field(description="DeepAgents/LangGraph 框架版本。")
    checkpointer_backend: str = Field(description="同 Thread messages 与 HITL 使用的 Checkpointer。")
    long_term_store_backend: str = Field(description="跨 Thread 长期 Memory 使用的 LangGraph Store。")
    backend_routes: dict[str, str] = Field(description="CompositeBackend 的路径路由及生命周期。")
    memory_namespace: list[str] = Field(description="长期 Memory namespace 维度，不包含具体用户值。")
    model_context_tokens: int = Field(description="当前 Summary Profile 使用的模型输入窗口。")
    summary_trigger_fraction: float = Field(description="接近 Context Window 时触发 Summary 的比例。")
    conversation_memory_enabled: bool = Field(description="相同 conversation_id 是否恢复历史 messages。")
    long_term_memory_enabled: bool = Field(description="相同用户是否可跨 Conversation 读取长期 Memory。")
    endpoints: dict[str, str] = Field(description="本版 Ask、Conversation、Memory、Audit 和 Artifact API。")
    sandbox: SandboxRuntimeStatus = Field(description="Artifact 工作区继续复用的 Core Sandbox Runtime。")


class DurableHealthResponse(BaseModel):
    """V3.17 Checkpoint、Repository、Store 和 Sandbox 健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="关键持久层全部可用时为 ok。")
    version: Literal["v3.17"] = Field(description="当前学习版本。")
    checkpoint_ready: bool = Field(description="LangGraph PostgreSQL Checkpointer 是否可读取。")
    repository_ready: bool = Field(description="Conversation/Run/Audit 表是否初始化。")
    long_term_store_ready: bool = Field(description="LangGraph PostgresStore 是否初始化。")
    sandbox_available: bool = Field(description="Docker Sandbox 是否可用。")
