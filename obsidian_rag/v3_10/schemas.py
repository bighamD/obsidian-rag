from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from obsidian_rag.v3_8_1.schemas import AgentAskRequest, AgentAskResponse, AgentNodeTiming


# V3.10 只描述运行外壳的生命周期，不改变 V3.8.1 Agent 图内的节点状态。
RunStatus = Literal["queued", "running", "succeeded", "failed"]


class ProductionAskRequest(AgentAskRequest):
    """`POST /agent/ask` 的输入，复用 V3.8.1 的 RAG、Context 与 Memory 配置。

    本版本不新增 Agent 行为参数；请求仍会进入 V3.8.1 的完整 LangGraph 链路，
    但外层会生成独立的 Production Run 记录。
    """


class RunEvent(BaseModel):
    """Run 生命周期中的一个可观察状态事件，不包含 LLM 的内部推理。"""

    name: str = Field(description="事件名称，例如 run_queued、run_started 或 run_succeeded。")
    status: RunStatus = Field(description="记录该事件时 Run 所处的生命周期状态。")
    occurred_at: str = Field(description="事件发生时间，UTC ISO 8601 格式。")
    detail: str = Field(description="面向调试的简短事件说明。")


class RunTiming(BaseModel):
    """一次 Run 的墙钟时间信息。"""

    started_at: str = Field(description="Run 开始执行时间，UTC ISO 8601 格式。")
    finished_at: str | None = Field(default=None, description="Run 结束时间；运行中时为 null。")
    duration_ms: int | None = Field(default=None, ge=0, description="从进入 Agent 到结束的墙钟耗时，单位毫秒。")


class TokenEstimate(BaseModel):
    """基于可观察文本的启发式 token 估算，不是模型供应商账单 token。"""

    answer_prompt_tokens: int = Field(description="实际 Answer prompt messages 的估算输入 token 数。")
    answer_output_tokens: int = Field(description="最终 answer 文本的估算输出 token 数。")
    observed_total_tokens: int = Field(description="上述两项之和；不含 Planner 与压缩 LLM 的不可观察用量。")
    method: str = Field(description="估算算法说明，明确其不是模型 tokenizer 或计费数据。")


class ToolRunSummary(BaseModel):
    """按工具名聚合的执行摘要，由 V3.8.1 的 StepResult 提取。"""

    tool_name: str = Field(description="实际执行的工具名称，例如 search_notes。")
    call_count: int = Field(description="该工具出现于初始步骤或 retry 步骤的总次数。")
    success_count: int = Field(description="status=success 的调用次数。")
    failed_count: int = Field(description="status=failed 的调用次数。")
    skipped_count: int = Field(description="status=skipped 的调用次数。")
    result_count: int = Field(description="该工具各次调用产出的检索结果总数。")


class RunMetrics(BaseModel):
    """一次已结束 Run 的聚合观测指标。"""

    timing: RunTiming = Field(description="总运行耗时。")
    token_estimate: TokenEstimate = Field(description="Answer prompt 与最终回答的启发式 token 摘要。")
    graph_node_count: int = Field(description="V3.8.1 实际经过的 LangGraph 节点数量。")
    trace_event_count: int = Field(description="V3.8.1 trace 中的可观察事件数量。")
    node_timings: list[AgentNodeTiming] = Field(description="每个 graph_path 节点的开始时间、结束时间和耗时。")
    retrieval_result_count: int = Field(description="初始检索和补搜步骤产出的结果总数。")
    tool_summaries: list[ToolRunSummary] = Field(description="按工具名聚合的调用成功率和结果数量。")


class RunError(BaseModel):
    """标准化失败摘要；保留可调试信息，不返回 Python traceback。"""

    error_type: str = Field(description="异常的 Python 类型名称。")
    message: str = Field(description="截断后的异常消息，用于定位失败原因。")
    retryable: bool = Field(description="本版本的保守重试建议；尚未引入自动重试策略。")


class RunRecord(BaseModel):
    """Production Core 管理的一次运行记录。

    `run_id` 是 V3.10 在调用 Agent 前生成的生命周期标识；`agent_run_id`
    是 V3.8.1 Agent 内部生成的图运行标识。两者故意分开，避免混淆编排层级。
    """

    run_id: str = Field(description="V3.10 Production Run 的唯一标识，可用于查询运行记录。")
    status: RunStatus = Field(description="当前或最终 Run 生命周期状态。")
    agent_run_id: str | None = Field(default=None, description="V3.8.1 Agent 成功返回后提供的内部 run_id。")
    conversation_id: str | None = Field(default=None, description="本次 Run 对应的对话标识；失败且未创建会话时为 null。")
    timing: RunTiming = Field(description="Run 的开始、结束和总耗时。")
    events: list[RunEvent] = Field(description="按时间顺序记录的生命周期状态事件。")
    metrics: RunMetrics | None = Field(default=None, description="成功完成后生成的工具、trace 和 token 估算摘要。")
    error: RunError | None = Field(default=None, description="失败时的标准化错误摘要；成功时为 null。")


class ProductionAskResponse(BaseModel):
    """V3.10 的统一 JSON 响应。

    `run` 是新的 Production Core 观测面；`agent_response` 保留 V3.8.1 的
    Plan、Context、Memory、证据和 trace 原始响应。Run 失败时后者为 null。
    """

    run: RunRecord = Field(description="本次请求的 V3.10 生命周期记录。")
    agent_response: AgentAskResponse | None = Field(default=None, description="成功时的完整 V3.8.1 Agent 响应；失败时为 null。")


class RuntimeConfigResponse(BaseModel):
    """可安全暴露给 Swagger 的运行时配置，不包含 API Key、数据库密码等敏感值。"""

    run_store: str = Field(description="Run Store 实现类型；本版为进程内存。")
    run_store_limit: int = Field(description="内存中最多保留的近期 Run 数。")
    token_estimation: str = Field(description="token 摘要所采用的估算方法与覆盖边界。")
