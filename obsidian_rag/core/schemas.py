from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from obsidian_rag.config import COLLECTION_NAME_PATTERN
from obsidian_rag.v1.schemas import SearchFilters, SearchHit, SearchMode

PlanStepKind = Literal["search", "synthesize", "no_search", "clarify"]
PlannerTraceStepType = Literal["planner_prompt", "planner_output", "planner_error"]


class PlanRequest(BaseModel):
    """公共 Planner 输入。"""

    question: str = Field(min_length=1, description="需要规划的当前问题。")
    top_k: int = Field(default=5, ge=1, le=20, description="每个检索步骤的候选结果数。")
    mode: SearchMode = Field(default="hybrid", description="Planner 应使用的检索模式。")
    filters: SearchFilters | None = Field(default=None, description="可选知识库元数据过滤条件。")
    max_steps: int = Field(default=4, ge=1, le=8, description="Planner 最多生成的步骤数。")


class PlanStep(BaseModel):
    """公共计划中的一个可执行步骤。"""

    id: str = Field(min_length=1, description="步骤唯一标识。")
    kind: PlanStepKind = Field(description="search、synthesize、no_search 或 clarify。")
    query: str | None = Field(default=None, description="search 步骤使用的查询词。")
    instruction: str | None = Field(default=None, description="非 search 步骤的执行说明。")
    depends_on: list[str] = Field(default_factory=list, description="该步骤依赖的前置步骤 ID。")
    reason: str | None = Field(default=None, description="生成该步骤的可观察原因。")


class Plan(BaseModel):
    """公共 Planner 的结构化计划。"""

    goal: str = Field(min_length=1, description="当前计划要完成的目标。")
    steps: list[PlanStep] = Field(min_length=1, description="按顺序执行的计划步骤。")


class PlannerTraceStep(BaseModel):
    """Planner 构造、调用和解析的可观察事件。"""

    node_name: str = Field(description="Planner 节点名称。")
    step_type: PlannerTraceStepType = Field(description="Planner 事件类型。")
    reason: str | None = Field(default=None, description="事件的简短可观察原因。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Planner 调试元数据。")


class PlanResponse(BaseModel):
    """公共 Planner 响应。"""

    question: str = Field(description="实际规划的问题。")
    plan: Plan = Field(description="结构化执行计划。")
    graph_path: list[str] = Field(description="Planner 实际节点顺序。")
    trace: list[PlannerTraceStep] = Field(description="Planner 可观察轨迹。")


# Planner 单步的执行状态：search 成功、非检索步骤跳过，或工具执行失败。
StepStatus = Literal["success", "skipped", "failed"]
# Agent 图中可观察的节点事件类型；它记录执行事实，不包含模型的内部推理过程。
AgentTraceStepType = Literal[
    "memory_read",
    "memory_compaction",
    "planner",
    "tool_result",
    "evidence_check",
    "retry",
    "context",
    "synthesize",
    "memory_write",
    "error",
]
AgentProgressPhase = Literal[
    "memory",
    "planning",
    "retrieval",
    "evidence",
    "context",
    "answer",
    "memory_write",
]
AgentProgressStatus = Literal["running", "completed", "failed"]


class AgentAskRequest(BaseModel):
    """`POST /agent/ask` 的输入参数。

    `memory_*` 控制会话历史的读取和压缩；`context_*` 控制 Answer 节点
    选择检索 chunks 的数量与其携带的预算配置；其余字段控制 RAG 检索和 Planner。
    """

    question: str = Field(min_length=1, description="当前用户问题。")
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="会话标识；为空时服务端会创建新的 conversation_id。",
    )
    memory_window: int = Field(default=3, ge=0, le=20, description="每次读取并携带的最近原始 Turn 数。")
    memory_compaction_enabled: bool = Field(default=True, description="是否在 Planner 前尝试压缩旧会话记忆。")
    memory_compaction_trigger_turns: int = Field(
        default=4,
        ge=1,
        le=100,
        description="待压缩旧 Turn 达到此数量时触发滚动摘要。",
    )
    memory_compaction_trigger_tokens: int = Field(
        default=3000,
        ge=100,
        le=50000,
        description="待压缩内容的估算 token 达到此值时触发滚动摘要，不是真实 tokenizer 数。",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="每个 search step 返回的最大检索结果数。")
    mode: SearchMode = Field(default="hybrid", description="检索模式：dense、keyword 或 hybrid。")
    filters: SearchFilters | None = Field(default=None, description="可选的知识库元数据过滤条件。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="本次检索使用的知识库 Collection；为空时使用 RAG_COLLECTION 默认值。",
    )
    max_steps: int = Field(default=4, ge=1, le=8, description="Planner 最多生成的执行步骤数。")
    max_retries: int = Field(default=1, ge=0, le=3, description="Evidence 不足时最多进行的补搜轮数。")
    context_max_chunks: int = Field(default=6, ge=1, le=20, description="最多选入 Answer prompt 的知识库 chunks 数。")
    context_token_budget: int = Field(
        default=4000,
        ge=500,
        le=20000,
        description="Answer context 的配置预算；当前版本不会按真实 tokenizer 截断。",
    )


class StepResult(BaseModel):
    """一个 Planner step 的执行结果。

    `search` step 会把 RAG 命中的原始知识库证据放进 `results`；
    `synthesize`、`no_search` 和 `clarify` 通常没有检索结果。
    """

    step_id: str = Field(description="对应 PlanStep 的唯一标识。")
    kind: str = Field(description="Planner 指定的步骤类型，如 search、synthesize 或 clarify。")
    tool_name: str | None = Field(default=None, description="实际调用的工具名称；非工具步骤可能为空。")
    query: str | None = Field(default=None, description="search 工具实际使用的检索词。")
    instruction: str | None = Field(default=None, description="非 search 步骤的执行说明。")
    status: StepStatus = Field(description="该步骤的最终执行状态。")
    result_count: int = Field(default=0, description="该步骤产出的检索结果数量。")
    results: list[SearchHit] = Field(default_factory=list, description="search step 命中的原始知识库结果。")
    sources: list[str] = Field(default_factory=list, description="从 results 提取的去重来源文件列表。")
    error: str | None = Field(default=None, description="工具失败时的错误信息。")
    reason: str | None = Field(default=None, description="Planner 为该步骤给出的执行原因。")


class AgentTraceStep(BaseModel):
    """一次 Agent 节点执行的结构化轨迹，用于调试和前端可观测性。

    `trace` 用来说明执行了哪些节点、工具和查询，不等同于模型 chain-of-thought。
    """

    node_name: str = Field(description="实际执行的 LangGraph 节点名称。")
    step_type: AgentTraceStepType = Field(description="节点执行事件的分类。")
    step_id: str | None = Field(default=None, description="关联的 Planner step 标识。")
    tool_name: str | None = Field(default=None, description="关联工具名称。")
    query: str | None = Field(default=None, description="关联检索查询。")
    result_count: int | None = Field(default=None, description="节点或工具产生的结果数量。")
    reason: str | None = Field(default=None, description="该事件的可观察原因说明。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="节点特有的调试元数据。")


class AgentNodeTiming(BaseModel):
    """一次 LangGraph 节点执行的墙钟耗时。"""

    node_name: str = Field(description="graph_path 中的 LangGraph 节点名称。")
    started_at: str = Field(description="节点开始时间，UTC ISO 8601 格式。")
    finished_at: str = Field(description="节点结束时间，UTC ISO 8601 格式。")
    duration_ms: int = Field(ge=0, description="节点执行耗时，单位毫秒。")


class EvidenceCheckResult(BaseModel):
    """Evidence Checker 对检索覆盖情况的判断结果。

    当 `is_sufficient` 为 false 时，`missing_step_ids` 和 `suggested_queries`
    会驱动 `retry_search` 进行补搜，最多次数由 `max_retries` 控制。
    """

    is_sufficient: bool = Field(description="所有需要检索的步骤是否已获得至少一条证据。")
    missing_points: list[str] = Field(default_factory=list, description="尚未覆盖的证据点说明。")
    suggested_queries: list[str] = Field(default_factory=list, description="Evidence Checker 建议用于补搜的查询词。")
    checked_step_ids: list[str] = Field(default_factory=list, description="已纳入证据检查的 search step 标识。")
    missing_step_ids: list[str] = Field(default_factory=list, description="没有检索到证据的 search step 标识。")
    retry_count: int = Field(default=0, description="当前请求已经执行的补搜轮数。")
    reason: str = Field(description="证据是否充分的判定原因。")


class ContextChunk(BaseModel):
    """一个来自 RAG 检索结果的知识库事实片段。

    它会进入 `ContextBundle.included_chunks`，并作为 Answer LLM 的
    `context_payload["included_chunks"]` 中的证据，而不是会话记忆。
    """

    step_id: str | None = Field(default=None, description="召回该 chunk 的 search step 标识。")
    chunk_id: str | None = Field(default=None, description="知识库中标注的 chunk_id，例如 KB-072。")
    source: str = Field(description="chunk 所属的知识库源文件。")
    topic: str | None = Field(default=None, description="chunk 的主题元数据。")
    score: float = Field(description="当前检索模式下用于排序的最终分数。")
    dense_rank: int | None = Field(default=None, description="dense 检索中的名次；非 dense/hybrid 结果可能为空。")
    keyword_rank: int | None = Field(default=None, description="keyword 检索中的名次；非 keyword/hybrid 结果可能为空。")
    dense_score: float | None = Field(default=None, description="dense 检索分数，仅用于调试观察。")
    keyword_score: float | None = Field(default=None, description="keyword 检索分数，仅用于调试观察。")
    hybrid_score: float | None = Field(default=None, description="RRF 或 hybrid 融合后的分数，仅用于调试观察。")
    text_preview: str = Field(description="实际送入 Answer prompt 的 chunk 文本预览。")
    text: str | None = Field(
        default=None,
        description="命中的原始 chunk 全文，仅用于 API/Console 调试展示，不会自动进入 Answer prompt。",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="原始检索 metadata，仅用于 API/Console 调试展示。")
    reason: str | None = Field(default=None, description="该 chunk 被选入或排除的原因。")


class ContextBundle(BaseModel):
    """Answer 节点的上下文构建产物。

    `messages[1]["content"]` 是真正传给 Answer LLM 的 JSON 字符串，包含：
    `question`、`plan`、`evidence_check`、`token_budget`、
    `conversation_summary`、`conversation_memory` 和 `included_chunks`。

    `included_chunks` 的 `text`、排序字段与 `metadata` 是 API/Console 的调试信息；
    真正的 Answer prompt 只使用其必要投影（包含 `text_preview`）。
    `excluded_chunks` 与 `context_summary` 仅用于 API 响应和调试观察，
    不会放进 Answer LLM 的 prompt。
    """

    messages: list[dict[str, str]] = Field(description="实际传给 Answer LLM 的 system/user messages。")
    included_chunks: list[ContextChunk] = Field(
        default_factory=list,
        description="已选入 Answer prompt 的知识库事实 chunks。",
    )
    excluded_chunks: list[ContextChunk] = Field(
        default_factory=list,
        description="因 max_chunks 或排序优先级而未选入 Answer prompt 的 chunks，仅供调试。",
    )
    token_budget: int = Field(
        description="Answer context 的配置预算。V3.8.1 会将其传给 LLM，但尚未按真实 tokenizer 截断 chunks。"
    )
    context_summary: str = Field(description="ContextBuilder 的构建结果摘要，仅供 API 响应和调试。")


class MemoryTurn(BaseModel):
    """MySQL 中保存的一轮原始对话，用作 `conversation_memory`。

    它保存原始用户问题和原始回答；旧 Turn 的压缩结果不在这里，
    而是保存在 `MemorySnapshot.summary_text`。
    """

    turn_id: str = Field(description="MySQL 原始 Turn 的唯一标识。")
    conversation_id: str = Field(description="该 Turn 所属的会话标识。")
    user_message: str = Field(description="该轮原始用户问题。")
    assistant_message: str = Field(description="该轮最终回答；不是压缩摘要。")
    sources: list[str] = Field(default_factory=list, description="该轮回答使用过的去重来源文件。")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="该轮执行过的工具调用摘要。")
    created_at: str = Field(description="Turn 创建时间，响应序列化时会转换为中国时区显示。")

    @field_validator("created_at", mode="before")
    @classmethod
    def format_created_at_for_china(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%y-%m-%d %H:%M:%S")


class MemorySnapshot(BaseModel):
    """当前请求读取到的会话记忆快照。

    `summary_text` 对应 Answer prompt 的 `conversation_summary`；
    `recent_turns` 对应 `conversation_memory`，其数量受 `memory_window` 控制。
    """

    conversation_id: str = Field(description="正在读取的会话标识。")
    window: int = Field(description="读取最近原始 Turn 时使用的 memory_window。")
    recent_turns: list[MemoryTurn] = Field(default_factory=list, description="实际放入 Planner 与 Answer 上下文的最近原始 Turns。")
    total_turn_count: int = Field(default=0, description="MySQL 中该会话保存的全部原始 Turn 数。")
    loaded_turn_count: int = Field(default=0, description="本次快照实际读取的 recent_turns 数量。")
    omitted_turn_count: int = Field(default=0, description="未进入 recent_turns 的原始 Turn 数量。")
    summary_text: str = Field(default="", description="已压缩旧 Turn 的滚动摘要；为空表示尚未生成摘要。")
    summary_through_turn_id: str | None = Field(default=None, description="当前摘要已覆盖到的最后一个原始 Turn。")
    summary_updated_at: str | None = Field(default=None, description="最近一次更新滚动摘要的时间。")


class MemoryCompactionResult(BaseModel):
    """`compact_memory` 节点的执行结果。

    `estimated_input_tokens` 是中文/其他字符比例的启发式估算，不是模型 tokenizer
    的真实 token 数；成功压缩后，`summary_text` 覆盖旧摘要并推进摘要截止 Turn。
    """

    conversation_id: str = Field(description="执行压缩检查的会话标识。")
    attempted: bool = Field(default=False, description="是否实际调用了摘要 LLM。")
    compacted: bool = Field(default=False, description="是否成功写入新的滚动摘要。")
    force: bool = Field(default=False, description="是否由手动强制压缩触发。")
    candidate_turn_count: int = Field(default=0, description="最近窗口之前、尚未被摘要的候选 Turn 数。")
    summarized_turn_count: int = Field(default=0, description="本次实际压缩进摘要的 Turn 数。")
    preserved_turn_count: int = Field(default=0, description="为保持最近对话连续性而保留原文的 Turn 数。")
    estimated_input_tokens: int = Field(default=0, description="候选 Turn 加旧摘要的启发式 token 估算值。")
    summary_text: str = Field(default="", description="本次成功生成或当前保留的滚动摘要。")
    summary_through_turn_id: str | None = Field(default=None, description="本次摘要覆盖到的最后一个 Turn 标识。")
    reason: str = Field(description="压缩、跳过或降级的原因。")


class MemoryCompactRequest(BaseModel):
    """`POST /memory/{conversation_id}/compact` 的手动压缩参数。

    `force=true` 会忽略 Turn 数和估算 token 阈值，但仍只压缩最近窗口之前的旧 Turn。
    """

    keep_recent_turns: int = Field(default=3, ge=0, le=20, description="压缩后仍保留原文的最近 Turn 数。")
    trigger_turns: int = Field(default=4, ge=1, le=100, description="候选旧 Turn 达到此数量时自动压缩。")
    trigger_tokens: int = Field(default=3000, ge=100, le=50000, description="候选内容的估算 token 达到此值时自动压缩。")
    force: bool = Field(default=True, description="是否忽略自动阈值并立即尝试压缩。")


class MemoryCompactResponse(BaseModel):
    """手动压缩后的压缩结果与最新 Memory 快照。"""

    compaction: MemoryCompactionResult = Field(description="本次手动压缩的执行结果。")
    memory_snapshot: MemorySnapshot = Field(description="压缩完成后重新读取到的会话记忆快照。")


class MemoryWriteResult(BaseModel):
    """本次 `/agent/ask` 完成时，当前原始问答 Turn 的 MySQL 写入结果。"""

    conversation_id: str = Field(description="写入目标会话标识。")
    turn_id: str | None = Field(default=None, description="成功写入时生成的原始 Turn 标识。")
    saved: bool = Field(description="当前问答是否已成功写入 MySQL。")
    reason: str | None = Field(default=None, description="写入失败时的原因。")


class AnswerStreamMetrics(BaseModel):
    """最终 Answer LLM 的流式传输观测，不包含 Prompt 或隐藏推理。"""

    mode: Literal["complete", "stream", "fallback"] = Field(description="Answer 使用的生成模式。")
    message_id: str | None = Field(default=None, description="流式答案消息标识；非流式时可为空。")
    llm_ttft_ms: int | None = Field(default=None, ge=0, description="首个可见文本 chunk 延迟；非流式时为空。")
    llm_reasoning_ttft_ms: int | None = Field(
        default=None,
        ge=0,
        description="首个 reasoning chunk 延迟；未开启或 provider 不支持时为空。",
    )
    llm_generation_ms: int = Field(default=0, ge=0, description="Answer LLM 生成阶段总耗时。")
    visible_character_count: int = Field(default=0, ge=0, description="最终可见答案字符数。")
    reasoning_character_count: int = Field(
        default=0,
        ge=0,
        description="学习调试 reasoning 字符数，不计入最终答案或 Memory。",
    )


class AgentProgressEvent(BaseModel):
    """面向用户体验的稳定 Agent 阶段事实，不暴露内部节点实现或隐藏推理。"""

    phase: AgentProgressPhase = Field(description="稳定业务阶段，不直接暴露 LangGraph 节点名称。")
    status: AgentProgressStatus = Field(description="当前阶段正在执行、已完成或执行失败。")
    collection: str | None = Field(default=None, description="检索阶段实际使用的知识库 Collection。")
    result_count: int | None = Field(default=None, ge=0, description="检索阶段累计获得的结果数量。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="可选的阶段事实元数据，不包含隐藏推理。")


class AgentEvent(BaseModel):
    """公共 Agent 事实事件；payload 不得包含模型隐藏推理。"""

    name: str = Field(description="事件名称，例如 node_finished 或 answer_delta。")
    data: dict[str, Any] = Field(default_factory=dict, description="节点、工具或可见文本增量数据。")


class AgentAskResponse(BaseModel):
    """`POST /agent/ask` 的完整可观测响应。

    `memory_snapshot` 是本轮 Planner/Answer 实际读取到的 Memory（压缩后、写入当前
    Turn 前）；当前问题及其回答是否已落盘，应通过 `memory_write` 判断。
    """

    run_id: str = Field(description="本次 Agent 执行的唯一标识。")
    conversation_id: str = Field(description="本次请求所在的会话标识。")
    question: str = Field(description="本次用户原始问题。")
    collection: str = Field(
        default="obsidian_notes",
        description="本次初始检索和 retry 检索实际使用的知识库 Collection。",
    )
    answer: str = Field(description="Agent 综合生成的最终回答。")
    used_retrieval: bool = Field(description="本次是否至少获得了一条 RAG 检索结果。")
    sources: list[str] = Field(description="最终检索结果使用到的去重来源文件。")
    plan: Plan = Field(description="Planner 输出的可执行计划。")
    step_results: list[StepResult] = Field(description="初始计划各步骤的执行结果。")
    retry_step_results: list[StepResult] = Field(description="Evidence 不足后补搜产生的步骤结果。")
    evidence_check: EvidenceCheckResult = Field(description="检索证据覆盖情况及补搜建议。")
    context_bundle: ContextBundle = Field(description="Answer 节点实际构造的上下文与调试信息。")
    memory_snapshot: MemorySnapshot = Field(description="Planner/Answer 使用的压缩后会话快照，不含当前新 Turn。")
    memory_compaction: MemoryCompactionResult = Field(description="本轮对旧会话记忆进行压缩的结果。")
    memory_write: MemoryWriteResult = Field(description="当前问答原始 Turn 的 MySQL 写入结果。")
    graph_path: list[str] = Field(description="本次实际经过的 LangGraph 节点顺序。")
    trace: list[AgentTraceStep] = Field(description="节点和工具的结构化执行轨迹。")
    node_timings: list[AgentNodeTiming] = Field(
        default_factory=list,
        description="按 graph_path 顺序记录每个 LangGraph 节点的开始时间、结束时间和耗时。",
    )
    answer_stream: AnswerStreamMetrics = Field(
        default_factory=lambda: AnswerStreamMetrics(mode="complete"),
        description="最终 Answer 的 streaming/fallback 模式与 TTFT 观测。",
    )
