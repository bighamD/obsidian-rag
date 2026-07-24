from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from obsidian_rag.core.schemas import AgentAskRequest
from obsidian_rag.v3_12.schemas import McpToolCallResponse, McpToolDefinition


McpTransport = Literal["stdio", "streamable_http"]
McpConnectionStatus = Literal["disconnected", "connecting", "connected", "degraded", "failed"]


class McpServerConfig(BaseModel):
    """一个生产形态 MCP Server 的配置，不直接保存认证 Secret。"""

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", description="Server 唯一名称，也是 Tool namespace 前缀。")
    description: str = Field(default="", description="Server 能力和业务边界说明。")
    enabled: bool = Field(default=True, description="是否加载并允许该 Server 的 Tool。")
    transport: McpTransport = Field(description="本地使用 stdio，远程服务优先使用 streamable_http。")
    command: str | None = Field(default=None, description="stdio Server 启动命令；HTTP Server 时为空。")
    args: list[str] = Field(default_factory=list, description="stdio Server 启动参数。")
    cwd: str | None = Field(default=None, description="stdio Server 工作目录；相对路径以 Registry 文件目录解析。")
    url: str | None = Field(default=None, description="Streamable HTTP MCP endpoint，例如 http://host/mcp。")
    headers_from_env: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP Header 到环境变量名称的映射；响应和 trace 不返回环境变量值。",
    )
    connect_on_startup: bool = Field(default=True, description="FastAPI lifespan 启动时是否预热连接。")
    timeout_seconds: float = Field(default=15, gt=0, le=120, description="连接、发现和调用的超时秒数。")
    tool_cache_ttl_seconds: int = Field(default=300, ge=5, le=3600, description="tools/list 缓存有效时间。")
    tool_allowlist: list[str] = Field(default_factory=list, description="允许注册的 Tool 名称；为空表示不注册任何 Tool。")

    @model_validator(mode="after")
    def validate_transport_fields(self) -> "McpServerConfig":
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio Server 必须配置 command")
        if self.transport == "streamable_http" and not self.url:
            raise ValueError("streamable_http Server 必须配置 url")
        return self


class McpServerRegistryConfig(BaseModel):
    """从 `mcp_servers.yaml` 加载的全部 MCP Server 配置。"""

    servers: list[McpServerConfig] = Field(default_factory=list, description="配置的 MCP Servers。")
    max_result_bytes: int = Field(default=262_144, ge=1024, le=10_485_760, description="单次 Tool Result 最大 JSON 字节数。")
    max_planner_tools: int = Field(default=24, ge=1, le=100, description="最多向 Planner 暴露的 MCP Tool 数量。")
    max_tool_schema_chars: int = Field(default=12_000, ge=1000, le=100_000, description="Tool Catalog input schema 总字符预算。")


class McpServerRuntime(BaseModel):
    """一个 MCP Server 当前连接、发现和调用状态。"""

    name: str = Field(description="Server namespace。")
    description: str = Field(description="Server 配置说明。")
    transport: McpTransport = Field(description="当前连接使用的 Transport。")
    status: McpConnectionStatus = Field(description="当前连接状态。")
    protocol_version: str | None = Field(default=None, description="initialize 协商出的 MCP protocol version。")
    tool_count: int = Field(default=0, ge=0, description="allowlist 过滤后缓存的 Tool 数量。")
    tool_names: list[str] = Field(default_factory=list, description="缓存的原始 MCP Tool 名称。")
    connected_at: str | None = Field(default=None, description="最近一次成功连接时间。")
    discovered_at: str | None = Field(default=None, description="最近一次成功 tools/list 时间。")
    call_count: int = Field(default=0, ge=0, description="进程生命周期内成功发起的 Tool 调用次数。")
    failure_count: int = Field(default=0, ge=0, description="连接、发现或调用失败次数。")
    last_error: str | None = Field(default=None, description="最近失败摘要，不包含 Secret。")


class McpRuntimeResponse(BaseModel):
    """Swagger 和 Agent Console 使用的 MCP Runtime 快照。"""

    registry_path: str = Field(description="实际加载的 MCP Server Registry 文件路径。")
    started: bool = Field(description="Connection Manager 后台事件循环是否已启动。")
    servers: list[McpServerRuntime] = Field(description="每个已配置 Server 的运行状态。")
    tools: list[McpToolDefinition] = Field(description="当前可注册到 Agent Tool Registry 的 MCP Tools。")
    errors: dict[str, str] = Field(default_factory=dict, description="按 Server 记录的连接或发现失败摘要。")


class McpRefreshResponse(BaseModel):
    """手动刷新 MCP 连接和 Tool Catalog 后的结果。"""

    refreshed_servers: list[str] = Field(description="本次尝试刷新的 Server 名称。")
    runtime: McpRuntimeResponse = Field(description="刷新后的完整 Runtime 快照。")


class McpAgentAskRequest(AgentAskRequest):
    """V3.12.3 完整 Agent 输入，在公共 Core 参数上增加 MCP Tool 控制。"""

    mcp_enabled: bool = Field(default=True, description="是否向 Planner 提供已连接的只读 MCP Tool Catalog。")
    mcp_tool_names: list[str] | None = Field(
        default=None,
        description="可选的请求级 Tool 收窄列表，必须是 server::tool；为空使用 Registry 中全部允许工具。",
    )


class McpExplicitToolCallRequest(BaseModel):
    """Swagger 中绕过 Planner、显式验证持久 MCP Session 的调用参数。"""

    name: str = Field(min_length=1, description="统一工具名称，例如 demo::get_server_time。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="满足 Tool input_schema 的结构化参数。")


class McpExplicitToolCallResponse(BaseModel):
    """显式 Tool 调用结果，同时保留 V3.12 MCP 协议响应。"""

    name: str = Field(description="统一 Tool 名称。")
    result: McpToolCallResponse = Field(description="持久 Session 返回并适配后的 MCP Tool Result。")


class McpAgentRuntimeConfigResponse(BaseModel):
    """V3.12.3 Agent、MCP 和 Console 能力说明。"""

    version: Literal["v3.12.3"] = Field(description="当前学习版本。")
    json_endpoint: str = Field(description="同步完整 Agent 响应路径。")
    stream_endpoint: str = Field(description="SSE Agent 运行路径。")
    mcp_runtime_endpoint: str = Field(description="MCP Server 和 Tool Catalog 状态路径。")
    transports: list[McpTransport] = Field(description="当前实现支持的 MCP Transports。")
    persistent_sessions: bool = Field(description="是否跨 Agent 请求复用 MCP Session。")
    planner_tool_selection: bool = Field(description="Planner 是否可以生成通用 tool step。")
    permission_policy_enabled: bool = Field(description="是否已启用 V3.13 Permission Policy。")
    sandbox_enabled: bool = Field(description="是否已启用 V3.14 Sandbox。")


class McpAgentHealthResponse(BaseModel):
    """V3.12.3 FastAPI 与 MCP Connection Manager 健康摘要。"""

    status: Literal["ok", "degraded"] = Field(description="API 可用且所有预期 Server 正常时为 ok。")
    version: Literal["v3.12.3"] = Field(description="当前学习版本。")
    mcp_started: bool = Field(description="MCP Connection Manager 是否已启动。")
    connected_servers: int = Field(ge=0, description="当前 connected 状态的 MCP Server 数。")
    configured_servers: int = Field(ge=0, description="当前启用的 MCP Server 数。")
