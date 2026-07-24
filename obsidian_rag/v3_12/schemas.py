from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


McpCallStatus = Literal["success", "failed"]


class McpServerInfo(BaseModel):
    """一个可由 V3.12 MCP Client 启动并连接的 Server 配置摘要。"""

    name: str = Field(description="MCP Server 在本地 Registry 中的唯一名称。")
    description: str = Field(description="Server 提供的能力和学习用途说明。")
    transport: Literal["stdio"] = Field(description="本版使用的 MCP Transport；当前固定为 stdio。")
    command: str = Field(description="启动 MCP Server 的可执行命令；不包含环境变量或 Secret。")
    args: list[str] = Field(description="启动 MCP Server 的命令参数。")
    timeout_seconds: float = Field(description="连接、发现或调用 MCP Tool 的最长等待秒数。")


class McpToolDefinition(BaseModel):
    """由远端 MCP Tool Schema 适配得到的稳定本地工具描述。"""

    server_name: str = Field(description="提供该工具的 MCP Server 名称。")
    name: str = Field(description="MCP Server 返回的原始工具名称。")
    namespaced_name: str = Field(description="带 Server 前缀的本地唯一名称，避免不同 Server 工具重名。")
    title: str | None = Field(default=None, description="MCP Tool 的可读标题；Server 未提供时为 null。")
    description: str | None = Field(default=None, description="MCP Tool 的用途说明。")
    input_schema: dict[str, Any] = Field(description="调用参数的 JSON Schema，来源于 MCP tools/list。")
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description="结构化返回值的 JSON Schema；Server 未声明时为 null。",
    )
    read_only: bool | None = Field(
        default=None,
        description="Server annotations 声明的只读提示；它不是安全授权结论。",
    )


class McpToolListResponse(BaseModel):
    """MCP 工具发现结果，保留单个 Server 失败而其他 Server 成功的边界。"""

    requested_server: str | None = Field(
        default=None,
        description="指定发现的 Server；为空表示遍历全部已配置 Server。",
    )
    tools: list[McpToolDefinition] = Field(description="成功通过 tools/list 发现并适配的工具。")
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="按 Server 名称记录发现失败原因；不会因为一个 Server 失败而丢弃其他结果。",
    )
    duration_ms: int = Field(description="本次工具发现总耗时，包含进程启动、initialize 和 tools/list。")
    trace: list["McpTraceEvent"] = Field(description="可观察协议阶段，不包含模型隐藏推理或敏感参数。")


class McpCallRequest(BaseModel):
    """通过 V3.12 MCP Client 显式调用一个远端工具。"""

    server_name: str = Field(description="目标 MCP Server 名称，例如 demo 或 rag。")
    tool_name: str = Field(description="tools/list 返回的原始工具名称。")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="传给 MCP tools/call 的结构化参数；必须满足工具 input_schema。",
    )


class McpContentBlock(BaseModel):
    """MCP CallToolResult 中一个 Content Block 的 JSON 投影。"""

    type: str = Field(description="Content Block 类型，例如 text、image、resource 或 resource_link。")
    payload: dict[str, Any] = Field(description="SDK Content Block 的完整 JSON 数据。")


class McpTraceEvent(BaseModel):
    """MCP Client 的可观察执行事实，用于 Swagger 和断点学习。"""

    phase: str = Field(description="协议阶段，例如 initialize、tools/list、tools/call 或 adapt_result。")
    server_name: str = Field(description="当前阶段关联的 MCP Server。")
    tool_name: str | None = Field(default=None, description="当前阶段关联的工具；发现阶段通常为 null。")
    status: Literal["success", "failed"] = Field(description="该阶段是否成功。")
    duration_ms: int = Field(description="该阶段或该失败路径的耗时。")
    detail: str = Field(description="不包含 Secret 和完整调用参数的简短说明。")


class McpToolCallResponse(BaseModel):
    """MCP tools/call 的统一 ToolResult，隔离官方 SDK 的协议对象。"""

    server_name: str = Field(description="实际调用的 MCP Server。")
    tool_name: str = Field(description="实际调用的 MCP Tool。")
    namespaced_name: str = Field(description="本地统一 Tool Registry 使用的 server::tool 唯一名称。")
    status: McpCallStatus = Field(description="调用是否成功；协议错误和 Tool isError 都映射为 failed。")
    is_error: bool = Field(description="MCP CallToolResult.isError；连接异常时同样为 true。")
    content: list[McpContentBlock] = Field(description="MCP 返回的文本、图片或资源等 Content Blocks。")
    structured_content: dict[str, Any] | None = Field(
        default=None,
        description="Server 返回的结构化结果；未提供时为 null。",
    )
    duration_ms: int = Field(description="从连接 Server 到结果适配完成的总耗时。")
    error: str | None = Field(default=None, description="失败原因；成功时为 null。")
    trace: list[McpTraceEvent] = Field(description="initialize、tools/list、tools/call 等协议阶段记录。")


class McpHealthResponse(BaseModel):
    """V3.12 FastAPI 服务健康状态。"""

    status: Literal["ok"] = Field(description="FastAPI 进程健康状态；不代表所有 MCP Server 已启动。")
    version: Literal["v3.12"] = Field(description="当前学习版本。")
    configured_servers: int = Field(description="当前可由 MCP Client 按需启动的 Server 数量。")
