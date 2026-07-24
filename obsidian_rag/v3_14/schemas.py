from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.core.permissions import PermissionPrincipal, PermissionReport
from obsidian_rag.core.sandbox import ArtifactRecord, SandboxRuntimeStatus
from obsidian_rag.v3_13.schemas import PermissionAskRequest


class SandboxAskRequest(PermissionAskRequest):
    """V3.14 Agent 输入：在 V3.13 完整请求上增加 Sandbox Catalog 开关。"""

    sandbox_enabled: bool = Field(default=True, description="是否向 Planner 提供受控 Sandbox Tool Catalog。")


class SandboxCallRequest(BaseModel):
    """Swagger 中显式调试一个 Sandbox Tool 的输入。"""

    run_id: str = Field(default="sandbox_debug", min_length=1, description="Workspace 与 Artifact 使用的 Run ID。")
    name: Literal[
        "sandbox::read_file",
        "sandbox::write_file",
        "sandbox::list_files",
        "sandbox::run_command",
    ] = Field(description="准备调用的 Sandbox Tool。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="满足目标 Tool JSON Schema 的参数。")
    principal: PermissionPrincipal = Field(description="执行前参与 V3.13 Policy 判断的主体。")


class SandboxCallResponse(BaseModel):
    """显式 Sandbox Tool 的权限决定和可选执行结果。"""

    permission: PermissionReport = Field(description="执行前的 allow/confirm/deny 报告。")
    executed: bool = Field(description="是否真正进入 Sandbox Runtime。")
    status: str = Field(description="ToolResult 状态；未执行时为 blocked。")
    data: Any = Field(default=None, description="Sandbox Tool 的结构化结果。")
    error: str | None = Field(default=None, description="失败或阻止原因。")


class SandboxArtifactListResponse(BaseModel):
    """一个 Run 的 Sandbox Artifacts。"""

    run_id: str = Field(description="查询的 Agent Run。")
    artifacts: list[ArtifactRecord] = Field(description="Workspace 中登记的文件。")


class SandboxRuntimeConfigResponse(BaseModel):
    """V3.14 Sandbox、Permission 与 Agent 能力摘要。"""

    version: Literal["v3.14", "v3.16"] = Field(description="提供 Sandbox Runtime 契约的学习版本。")
    json_endpoint: str = Field(description="同步 Agent JSON 路径。")
    stream_endpoint: str = Field(description="Agent SSE 路径。")
    sandbox_call_endpoint: str = Field(description="显式 Sandbox Tool 调试路径。")
    artifacts_endpoint: str = Field(description="Artifact 列表路径模板。")
    sandbox: SandboxRuntimeStatus = Field(description="Docker Backend 和固定 Profile 状态。")
    permission_policy_enabled: bool = Field(description="Sandbox Tool 是否仍经过 V3.13 Policy。")
    skill_router_enabled: bool = Field(description="是否保留 Core Skill Router。")
    approval_resume_enabled: bool = Field(description="是否支持 confirm 后 LangGraph resume。")


class SandboxHealthResponse(BaseModel):
    """V3.14 API、Docker Sandbox 和 MCP 健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="Docker 与关键依赖可用时为 ok。")
    version: Literal["v3.14"] = Field(description="当前学习版本。")
    sandbox_available: bool = Field(description="Docker Sandbox 是否可执行。")
    docker_version: str | None = Field(default=None, description="Docker Server Version。")
    permission_policy_enabled: bool = Field(description="Policy Engine 是否启用。")
    connected_mcp_servers: int = Field(ge=0, description="已连接 MCP Server 数。")
