from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.v3_4.schemas import Plan
from obsidian_rag.v3_8_1.schemas import (
    AgentAskRequest,
    ContextBundle,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
    StepResult,
)


AdvancedTraceKind = Literal[
    "subgraph",
    "command",
    "send",
    "retry_policy",
    "evidence",
    "context",
    "messages",
    "memory",
]


class AdvancedAskRequest(AgentAskRequest):
    """V3.10.3 Advanced Graph 的输入。

    继承 V3.8.1 的 RAG、Memory、Context 参数；新增字段只控制 LangGraph
    高级模式的教学行为，不改变知识库内容或检索算法。
    """

    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="LangGraph Checkpointer 使用的线程标识；为空时服务端为本次 Run 创建独立 thread_id。",
    )
    max_parallel_searches: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Planner 产生多个 search step 时，最多通过 Send 并行分发多少个检索任务。",
    )
    simulate_transient_search_failure: bool = Field(
        default=False,
        description="教学开关：让每个初始 search_worker 首次抛出临时异常，用于观察 RetryPolicy 自动重试。",
    )


class SearchTask(BaseModel):
    """由 Planner search step 转换得到的 Send 并行任务。"""

    step_id: str = Field(description="对应的 Planner step ID。")
    query: str = Field(description="发送给本地混合检索的查询词。")
    reason: str | None = Field(default=None, description="Planner 说明为什么需要该检索任务。")


class AdvancedTraceStep(BaseModel):
    """V3.10.3 高级执行轨迹，只记录可观察事实，不包含隐藏推理。"""

    node_name: str = Field(description="产生该事件的主图或子图节点名称。")
    kind: AdvancedTraceKind = Field(description="事件对应的高级 LangGraph 能力类别。")
    detail: str = Field(description="面向学习和调试的简短事实说明。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="节点、任务、路由或重试的结构化元数据。")


class RouteDecision(BaseModel):
    """Command 节点做出的动态跳转记录。"""

    node_name: str = Field(description="返回 Command 的节点名称。")
    destination: str = Field(description="Command.goto 选择的目标节点。")
    reason: str = Field(description="选择该目标节点的可观察业务原因。")


class StateHistoryEntry(BaseModel):
    """一个 LangGraph Checkpoint 的轻量 State 快照摘要。"""

    checkpoint_id: str | None = Field(default=None, description="Checkpointer 为该状态生成的 checkpoint_id。")
    created_at: str | None = Field(default=None, description="Checkpoint 创建时间。")
    next_nodes: list[str] = Field(default_factory=list, description="从该状态继续执行时的下一批节点。")
    state_keys: list[str] = Field(default_factory=list, description="该快照中存在的 AgentState 字段名称。")
    graph_path: list[str] = Field(default_factory=list, description="截至该快照已经记录的主图执行路径。")
    step_result_count: int = Field(default=0, description="截至该快照已经合并的初始并行检索结果数量。")
    retry_result_count: int = Field(default=0, description="截至该快照已经合并的业务补搜结果数量。")
    answer_preview: str = Field(default="", description="如果已经生成答案，返回前 160 字符；不返回隐藏推理。")


class StateHistoryResponse(BaseModel):
    """Swagger/CLI 查询某个 thread_id 的 State History 响应。"""

    thread_id: str = Field(description="查询的 LangGraph thread_id。")
    entries: list[StateHistoryEntry] = Field(description="按 Checkpointer 返回顺序排列的 State 快照摘要。")


class AdvancedAskResponse(BaseModel):
    """V3.10.3 Advanced Graph 的完整 JSON 响应。

    `memory_snapshot` 是 Planner/Answer 实际使用的原始 Turn 窗口和滚动摘要；
    `context_bundle.messages` 是实际 Answer Prompt；知识库 chunk 仍位于
    `context_bundle.included_chunks`，而 State History 只返回轻量摘要。
    """

    run_id: str = Field(description="本次 V3.10.3 Advanced Run 标识。")
    thread_id: str = Field(description="Checkpointer 和 State History 使用的 LangGraph thread_id。")
    conversation_id: str = Field(description="MySQL Conversation Memory 使用的会话标识。")
    question: str = Field(description="本轮用户原始问题。")
    answer: str = Field(description="messages stream 聚合后的最终答案。")
    used_retrieval: bool = Field(description="是否至少有一个 Send/retry 检索任务获得知识库结果。")
    sources: list[str] = Field(description="并行检索与补搜结果中的去重来源文件。")
    plan: Plan = Field(description="Planner 子图生成的结构化计划。")
    planner_subgraph_path: list[str] = Field(description="Planner 子图内部实际经过的节点顺序。")
    graph_path: list[str] = Field(description="主图节点执行记录；并行 worker 会带任务后缀。")
    step_results: list[StepResult] = Field(description="Send 并行执行产生的初始检索结果。")
    retry_step_results: list[StepResult] = Field(description="Evidence 业务补搜产生的结果；不同于 RetryPolicy 节点异常重试。")
    evidence_check: EvidenceCheckResult = Field(description="并行结果合并后的证据充分性判断。")
    context_bundle: ContextBundle = Field(description="Answer 节点实际使用的 Prompt、知识库 chunks 与调试信息。")
    memory_snapshot: MemorySnapshot = Field(description="Planner/Answer 使用的滚动摘要和最近原始 Turns。")
    memory_compaction: MemoryCompactionResult = Field(description="本轮 Planner 前的 Memory Compaction 结果。")
    memory_write: MemoryWriteResult = Field(description="最终答案写入 MySQL Conversation Memory 的结果。")
    trace: list[AdvancedTraceStep] = Field(description="Subgraph、Send、Command、RetryPolicy 和 messages 的高级轨迹。")
    route_decisions: list[RouteDecision] = Field(description="Command 动态路由的完整记录。")
    node_retry_counts: dict[str, int] = Field(description="每个并行 search worker 的实际节点执行次数。")
    parallel_task_count: int = Field(description="本轮通过 Send 分发的初始并行检索任务数。")
    state_history_count: int = Field(description="当前 thread_id 可查询到的 checkpoint 数量。")
    stream_modes: list[str] = Field(description="SSE 使用的 LangGraph stream modes。")


class AdvancedStreamConfigResponse(BaseModel):
    """前端或 Swagger 可读取的 V3.10.3 非敏感流式配置。"""

    json_endpoint: str = Field(description="Advanced Graph 的 JSON 接口路径。")
    stream_endpoint: str = Field(description="Advanced Graph 的 SSE 接口路径。")
    history_endpoint_template: str = Field(description="State History 查询接口模板。")
    stream_modes: list[str] = Field(description="当前启用的 LangGraph stream modes。")
    checkpointer: str = Field(description="当前 Checkpointer 实现及其持久化边界。")

