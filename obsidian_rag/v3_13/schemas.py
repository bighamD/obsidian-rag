from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from obsidian_rag.core.permissions.schemas import (
    PermissionAuditRecord,
    PermissionEvaluateAction,
    PermissionPrincipal,
    PermissionReport,
)
from obsidian_rag.core.skills.schemas import SkillManifest, SkillSelection
from obsidian_rag.v3_12_3.schemas import McpTransport
from obsidian_rag.v3_12.schemas import McpToolCallResponse
from obsidian_rag.v3_12_4.schemas import RoutedMcpAskRequest


class PermissionAskRequest(RoutedMcpAskRequest):
    """V3.13 Agent 输入：在 V3.12.4 路由与 MCP 参数上增加调用主体。"""

    principal: PermissionPrincipal = Field(
        default_factory=PermissionPrincipal,
        description="本轮 Policy Engine 使用的主体权限、Tool allowlist 和 Collection scope。",
    )
    skill_router_enabled: bool = Field(
        default=True,
        description="是否在 Planner 前调用 Core LLM Skill Router。",
    )
    skill_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="可选的强制 Skill 名称；填写后跳过 LLM Skill Router。",
    )


class SkillRouteDebugRequest(BaseModel):
    """只执行 Skill 发现与选择、不进入 Planner 的 Swagger 调试输入。"""

    question: str = Field(min_length=1, description="用于选择 Skill 的原始问题。")
    skill_router_enabled: bool = Field(default=True, description="是否允许调用 LLM Skill Router。")
    skill_name: str | None = Field(default=None, min_length=1, description="可选的强制 Skill 名称。")


class SkillRouteDebugResponse(BaseModel):
    """独立 Skill Router 调试结果，不执行 Agent Plan 或 Tool。"""

    question: str = Field(description="原始问题。")
    selection: SkillSelection = Field(description="Skill Router 的结构化选择结果。")


class SkillRuntimeResponse(BaseModel):
    """Core Skill Registry 的安全运行时快照。"""

    root: str = Field(description="实际扫描 SKILL.md 的根目录。")
    skills: list[SkillManifest] = Field(description="当前发现的有效 Skill manifests。")
    errors: list[str] = Field(default_factory=list, description="发现阶段跳过的无效 Skill 摘要。")


class PermissionEvaluateRequest(BaseModel):
    """不执行 Tool、只观察 Policy Decision 的 Swagger 调试输入。"""

    principal: PermissionPrincipal = Field(default_factory=PermissionPrincipal, description="参与策略判断的主体。")
    action: PermissionEvaluateAction = Field(description="准备执行但不会真正调用的 search/tool 动作。")


class PermissionEvaluateResponse(BaseModel):
    """独立 Policy 调试结果；不会进入 Tool Executor。"""

    report: PermissionReport = Field(description="该动作对应的完整 allow/confirm/deny 报告。")


class PermissionMcpCallRequest(BaseModel):
    """显式 MCP Tool 调试调用；同样必须先经过 V3.13 Policy。"""

    name: str = Field(min_length=1, description="统一 MCP Tool 名称，例如 demo::get_server_time。")
    arguments: dict = Field(default_factory=dict, description="满足 MCP Tool input_schema 的参数。")
    principal: PermissionPrincipal = Field(default_factory=PermissionPrincipal, description="执行本次调用的主体。")


class PermissionMcpCallResponse(BaseModel):
    """显式 MCP Tool 的权限决定与可选执行结果。"""

    permission: PermissionReport = Field(description="执行前产生的权限报告。")
    executed: bool = Field(description="Tool 是否真正进入 McpConnectionManager。")
    result: McpToolCallResponse | None = Field(default=None, description="仅 allow 时返回的 MCP 调用结果。")


class PermissionAuditListResponse(BaseModel):
    """进程内 Permission Audit Store 的最近记录。"""

    persistence: Literal["in_memory"] = Field(description="V3.13 审计记录只保存在当前 API 进程。")
    records: list[PermissionAuditRecord] = Field(description="按创建时间倒序排列的审计记录。")


class PermissionRuntimeConfigResponse(BaseModel):
    """V3.13 Permission Policy、Agent 与外围 Runtime 能力说明。"""

    version: Literal["v3.13"] = Field(description="当前学习版本。")
    json_endpoint: str = Field(description="同步完整 Agent 响应路径。")
    stream_endpoint: str = Field(description="SSE Agent 运行路径。")
    evaluate_endpoint: str = Field(description="不执行 Tool 的独立 Policy 调试路径。")
    audit_endpoint: str = Field(description="读取进程内权限审计记录的路径。")
    transports: list[McpTransport] = Field(description="继续支持的 MCP Transports。")
    collection_routing: bool = Field(description="是否保留 V3.12.4 Collection Router。")
    multi_collection_retrieval: bool = Field(description="是否保留多 Collection 检索。")
    permission_policy_enabled: bool = Field(description="是否在 Tool Executor 前启用统一 Policy。")
    skill_router_enabled: bool = Field(description="是否在 Planner 前启用 Core Skill Router。")
    decisions: list[Literal["allow", "confirm", "deny"]] = Field(description="当前策略支持的决定类型。")
    approval_resume_enabled: bool = Field(description="是否已支持真正的人工审批暂停和恢复。")
    sandbox_enabled: bool = Field(description="是否已启用隔离执行环境。")


class PermissionHealthResponse(BaseModel):
    """V3.13 API、MCP、知识库和 Permission Policy 健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="关键依赖可用时为 ok。")
    version: Literal["v3.13"] = Field(description="当前学习版本。")
    permission_policy_enabled: bool = Field(description="Policy Engine 是否已注入 Agent。")
    mcp_started: bool = Field(description="MCP Connection Manager 是否已启动。")
    connected_mcp_servers: int = Field(ge=0, description="当前已连接 MCP Server 数。")
    enabled_knowledge_bases: int = Field(ge=0, description="当前可路由知识库数量。")
