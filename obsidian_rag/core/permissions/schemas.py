from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ToolRiskLevel = Literal["safe", "confirm", "restricted"]
PermissionDecisionKind = Literal["allow", "confirm", "deny"]


class PermissionPrincipal(BaseModel):
    """发起 Agent Run 的最小身份与授权范围，不包含认证凭据。"""

    subject_id: str = Field(default="learner", min_length=1, description="当前调用主体的稳定标识。")
    roles: list[str] = Field(default_factory=lambda: ["user"], description="当前主体拥有的角色名称。")
    permissions: list[str] = Field(
        default_factory=lambda: ["knowledge.read", "tool.read"],
        description="允许使用的权限字符串；星号表示全部静态权限。",
    )
    tool_allowlist: list[str] = Field(
        default_factory=lambda: ["search_notes", "demo::*"],
        description="允许请求的 Tool 名称模式，支持 fnmatch 星号匹配。",
    )
    allowed_collections: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许检索的知识库 Collection 模式；星号表示所有已路由知识库。",
    )


class PermissionDecision(BaseModel):
    """Policy Engine 对一个 PlanStep 的结构化执行决定。"""

    step_id: str = Field(description="被检查的 Planner step 标识。")
    kind: str = Field(description="步骤类型，例如 search、tool 或 synthesize。")
    tool_name: str | None = Field(default=None, description="步骤准备调用的统一 Tool 名称。")
    source: str = Field(default="agent", description="工具来源，例如 local、mcp 或 agent。")
    risk_level: ToolRiskLevel = Field(description="工具风险等级：safe、confirm 或 restricted。")
    decision: PermissionDecisionKind = Field(description="最终策略决定：allow、confirm 或 deny。")
    reason: str = Field(description="不包含隐藏推理的可观察决策原因。")
    required_permissions: list[str] = Field(default_factory=list, description="该步骤要求的权限字符串。")
    missing_permissions: list[str] = Field(default_factory=list, description="当前 Principal 缺失的权限。")
    collections: list[str] = Field(default_factory=list, description="search 步骤准备访问的 Collections。")
    denied_collections: list[str] = Field(default_factory=list, description="超出 Principal Collection scope 的知识库。")
    argument_names: list[str] = Field(default_factory=list, description="参与校验的参数名称，不回显参数值或 Secret。")
    validation_errors: list[str] = Field(default_factory=list, description="JSON Schema 参数校验失败摘要。")


class PermissionReport(BaseModel):
    """一次 Agent Run 在执行前产生的完整权限检查结果。"""

    principal: PermissionPrincipal = Field(description="本次检查使用的主体、权限和 scope 快照。")
    decisions: list[PermissionDecision] = Field(description="按 Plan 顺序排列的逐步骤权限决定。")
    allow_count: int = Field(ge=0, description="允许自动执行的步骤数量。")
    confirm_count: int = Field(ge=0, description="需要人工确认、当前版本不会自动执行的步骤数量。")
    deny_count: int = Field(ge=0, description="被策略拒绝的步骤数量。")
    all_allowed: bool = Field(description="所有步骤是否都可以立即执行。")
    summary: str = Field(description="本轮权限检查的简短摘要。")


class PermissionAuditRecord(BaseModel):
    """保存到审计 Store 的一次权限检查快照。"""

    audit_id: str = Field(description="审计记录唯一标识。")
    run_id: str = Field(description="关联 Agent Run 标识。")
    conversation_id: str = Field(description="关联会话标识。")
    created_at: str = Field(description="审计记录创建时间，UTC ISO 8601。")
    report: PermissionReport = Field(description="当时产生的完整 PermissionReport。")


class PermissionEvaluateAction(BaseModel):
    """独立 Swagger Policy 调试接口使用的单个动作。"""

    step_id: str = Field(default="policy_debug", min_length=1, description="调试动作标识。")
    kind: Literal["search", "tool"] = Field(description="调试 search 或通用 tool 权限。")
    tool_name: str | None = Field(default=None, description="tool 动作的统一工具名称；search 可为空。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="用于 JSON Schema 校验的 Tool 参数。")
    collections: list[str] = Field(default_factory=list, description="search 动作准备访问的 Collections。")
