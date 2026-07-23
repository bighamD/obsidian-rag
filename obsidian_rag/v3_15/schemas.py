from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from obsidian_rag.core.permissions import PermissionDecision, PermissionReport
from obsidian_rag.core.schemas import AgentAskResponse, PlanStep
from obsidian_rag.v3_10.schemas import ProductionAskResponse, RunRecord
from obsidian_rag.v3_14.schemas import SandboxAskRequest


ApprovalAction = Literal["allow", "deny", "edit"]
ApprovalStatus = Literal["pending", "resolved"]


class HitlAskRequest(SandboxAskRequest):
    """V3.15 Agent 输入：继承 V3.14 完整能力，并允许命中 confirm 后暂停。"""


class ApprovalStep(BaseModel):
    """一次待审批 Tool Step 的可见快照。"""

    step_id: str = Field(description="Planner 生成的步骤 ID，用于关联 PermissionDecision 和恢复参数。")
    tool_name: str = Field(description="等待人工确认的 Tool 名称。")
    reason: str = Field(description="Permission Policy 要求确认的原因。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="暂停时即将提交给 Tool 的参数。")
    risk_level: str = Field(description="Tool 的风险等级，V3.15 通常为 confirm。")


class ApprovalRequest(BaseModel):
    """LangGraph interrupt 暂停时交给 API、前端和持久 Store 的审批请求。"""

    approval_id: str = Field(description="审批请求唯一标识；同一个 Run 重放 approval_gate 时保持稳定。")
    run_id: str = Field(description="被暂停的 Agent Run，也是 LangGraph thread_id。")
    conversation_id: str = Field(description="本次运行所属的 Conversation Memory 标识。")
    status: Literal["pending"] = Field(default="pending", description="新建审批始终处于 pending。")
    summary: str = Field(description="面向审批人的简短风险摘要。")
    steps: list[ApprovalStep] = Field(description="本次需要一起审批的 confirm 步骤。")
    permission_report: PermissionReport = Field(description="暂停前完整的 allow/confirm/deny 权限报告。")
    created_at: str = Field(description="审批请求首次写入 PostgreSQL 的 UTC ISO 8601 时间。")


class ApprovalDecisionInput(BaseModel):
    """用户对一个暂停 Run 提交的恢复决定。"""

    action: ApprovalAction = Field(description="allow 全部允许、deny 全部拒绝、edit 修改参数后允许。")
    comment: str | None = Field(default=None, max_length=500, description="审批备注，仅用于审计和学习观察。")
    step_arguments: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="action=edit 时按 step_id 提供替换后的 Tool arguments。",
    )

    @model_validator(mode="after")
    def validate_edit_arguments(self):
        if self.action == "edit" and not self.step_arguments:
            raise ValueError("action=edit 时必须提供 step_arguments。")
        return self


class ApprovalDecision(BaseModel):
    """已持久化并传给 LangGraph Command(resume=...) 的审批决定。"""

    approval_id: str = Field(description="对应的审批请求 ID。")
    run_id: str = Field(description="对应的 Agent Run / LangGraph thread_id。")
    action: ApprovalAction = Field(description="本次恢复采用的审批动作。")
    comment: str | None = Field(default=None, description="审批备注。")
    step_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict, description="编辑后的逐步骤 Tool 参数。")
    decided_at: str = Field(description="决定写入 PostgreSQL 的 UTC ISO 8601 时间。")


class ApprovalRecord(BaseModel):
    """PostgreSQL 中一个审批请求的完整状态。"""

    request: ApprovalRequest = Field(description="interrupt 时生成的原始审批请求。")
    status: ApprovalStatus = Field(description="pending 表示 Graph 暂停；resolved 表示已经提交决定。")
    decision: ApprovalDecision | None = Field(default=None, description="resolved 后保存的决定；pending 时为 null。")
    resolved_at: str | None = Field(default=None, description="审批完成时间；pending 时为 null。")


class ApprovalResumeRequest(ApprovalDecisionInput):
    """`POST /approvals/{run_id}/resume` 的 JSON 请求体。"""


class HitlAskResponse(ProductionAskResponse):
    """V3.15 JSON/SSE 统一响应，增加可选审批状态。"""

    run: RunRecord = Field(description="支持 waiting_for_approval 的持久 Run 生命周期。")
    agent_response: AgentAskResponse | None = Field(
        default=None,
        description="完成时是完整响应；暂停时是 approval_gate 前的部分 AgentState 快照。",
    )
    approval: ApprovalRecord | None = Field(default=None, description="暂停或恢复后的审批记录；无审批时为 null。")


class ApprovalListResponse(BaseModel):
    """Swagger 查询当前待审批请求的响应。"""

    approvals: list[ApprovalRecord] = Field(description="按创建时间倒序排列的审批记录。")


class HitlRuntimeConfigResponse(BaseModel):
    """V3.15 Checkpoint、审批和恢复能力摘要。"""

    version: Literal["v3.15"] = Field(description="当前学习版本。")
    checkpoint_backend: str = Field(description="LangGraph 持久 Checkpointer 实现。")
    runtime_store_backend: str = Field(description="Run、Approval 和幂等结果的持久化实现。")
    postgres_location: str = Field(description="已隐藏密码的 PostgreSQL 连接位置。")
    postgres_database: str = Field(description="V3.15 使用的 PostgreSQL 数据库名。")
    postgres_schema: str = Field(description="Checkpoint 与 HITL Runtime 表所在 Schema。")
    interrupt_enabled: bool = Field(description="confirm 是否会触发 LangGraph interrupt。")
    resume_enabled: bool = Field(description="是否支持 Command(resume=...)。")
    idempotency_enabled: bool = Field(description="副作用 Tool 是否使用持久幂等结果缓存。")
    json_endpoint: str = Field(description="新建 Agent Run 的同步 JSON 路径。")
    stream_endpoint: str = Field(description="新建 Agent Run 的 SSE 路径。")
    approval_endpoint: str = Field(description="查询审批记录的路径模板。")
    resume_endpoint: str = Field(description="提交决定并恢复 Graph 的 JSON 路径模板。")
    resume_stream_endpoint: str = Field(description="提交决定并通过 SSE 恢复 Graph 的路径模板。")
    recovery_endpoint: str = Field(description="失败 Run 从最近 Checkpoint 重试的 JSON 路径模板。")
    recovery_stream_endpoint: str = Field(description="失败 Run 从最近 Checkpoint 重试的 SSE 路径模板。")


class HitlHealthResponse(BaseModel):
    """V3.15 API 与持久恢复组件健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="Checkpoint、Runtime Store 和 Sandbox 可用时为 ok。")
    version: Literal["v3.15"] = Field(description="当前学习版本。")
    checkpoint_ready: bool = Field(description="PostgresSaver 是否已创建并可读写。")
    runtime_store_ready: bool = Field(description="Run、Approval 和幂等表是否已初始化。")
    sandbox_available: bool = Field(description="V3.14 Docker Sandbox 是否可执行。")
    connected_mcp_servers: int = Field(ge=0, description="当前已连接的 MCP Server 数量。")


class HitlExecutionResult(BaseModel):
    """Agent 层交给 Runtime 层的内部执行结果。"""

    status: Literal["waiting_for_approval", "succeeded"] = Field(description="本次 invoke 是暂停还是完成。")
    run_id: str = Field(description="Agent Run / LangGraph thread_id。")
    response: AgentAskResponse = Field(description="当前 checkpoint 对应的 Agent 响应快照。")
    approval: ApprovalRecord | None = Field(default=None, description="暂停或已恢复的审批记录。")


def approval_steps_from_plan(
    steps: list[PlanStep],
    decisions: list[PermissionDecision],
) -> list[ApprovalStep]:
    """把 confirm PermissionDecision 与 Planner Step 合并成前端可审批结构。"""

    by_id = {step.id: step for step in steps}
    return [
        ApprovalStep(
            step_id=decision.step_id,
            tool_name=decision.tool_name or "unknown",
            reason=decision.reason,
            arguments=dict(by_id[decision.step_id].arguments) if decision.step_id in by_id else {},
            risk_level=decision.risk_level,
        )
        for decision in decisions
        if decision.decision == "confirm"
    ]
