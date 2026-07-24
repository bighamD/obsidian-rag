from __future__ import annotations

import asyncio
import json
from time import perf_counter

from obsidian_rag.v3_12.client.adapter import adapt_content, adapt_tool, structured_content
from obsidian_rag.v3_12.client.manager import McpClientManager
from obsidian_rag.v3_12.schemas import (
    McpCallRequest,
    McpServerInfo,
    McpToolCallResponse,
    McpToolDefinition,
    McpToolListResponse,
    McpTraceEvent,
)


class McpIntegrationService:
    """在 FastAPI/CLI 与 MCP SDK 之间提供稳定的应用服务边界。"""

    def __init__(self, manager: McpClientManager, max_result_bytes: int = 262_144):
        self.manager = manager
        self.max_result_bytes = max_result_bytes

    def list_servers(self) -> list[McpServerInfo]:
        return [
            McpServerInfo(
                name=server.name,
                description=server.description,
                transport="stdio",
                command=server.command,
                args=list(server.args),
                timeout_seconds=server.timeout_seconds,
            )
            for server in self.manager.list_servers()
        ]

    async def list_tools(self, server_name: str | None = None) -> McpToolListResponse:
        started = perf_counter()
        servers = [self.manager.get_server(server_name)] if server_name else self.manager.list_servers()
        tools: list[McpToolDefinition] = []
        errors: dict[str, str] = {}
        trace: list[McpTraceEvent] = []

        for server in servers:
            server_started = perf_counter()
            try:
                discovery = await self.manager.discover_tools(server.name)
            except Exception as exc:
                message = _safe_error_message(exc)
                errors[server.name] = message
                trace.append(
                    McpTraceEvent(
                        phase="tools/list",
                        server_name=server.name,
                        status="failed",
                        duration_ms=_elapsed_ms(server_started),
                        detail=message,
                    )
                )
                continue
            trace.extend(
                [
                    McpTraceEvent(
                        phase="initialize",
                        server_name=server.name,
                        status="success",
                        duration_ms=discovery.initialize_ms,
                        detail=f"MCP Session 初始化完成，protocol={discovery.protocol_version}。",
                    ),
                    McpTraceEvent(
                        phase="tools/list",
                        server_name=server.name,
                        status="success",
                        duration_ms=discovery.list_tools_ms,
                        detail=f"发现 {len(discovery.tools)} 个工具。",
                    ),
                ]
            )
            tools.extend(adapt_tool(server.name, tool) for tool in discovery.tools)

        return McpToolListResponse(
            requested_server=server_name,
            tools=tools,
            errors=errors,
            duration_ms=_elapsed_ms(started),
            trace=trace,
        )

    async def call_tool(self, request: McpCallRequest) -> McpToolCallResponse:
        started = perf_counter()
        trace: list[McpTraceEvent] = []
        try:
            protocol_call = await self.manager.call_tool(
                request.server_name,
                request.tool_name,
                request.arguments,
            )
        except Exception as exc:
            message = _safe_error_message(exc)
            trace.append(
                McpTraceEvent(
                    phase="tools/call",
                    server_name=request.server_name,
                    tool_name=request.tool_name,
                    status="failed",
                    duration_ms=_elapsed_ms(started),
                    detail=message,
                )
            )
            return McpToolCallResponse(
                server_name=request.server_name,
                tool_name=request.tool_name,
                namespaced_name=f"{request.server_name}::{request.tool_name}",
                status="failed",
                is_error=True,
                content=[],
                duration_ms=_elapsed_ms(started),
                error=message,
                trace=trace,
            )

        result = protocol_call.result
        trace.extend(
            [
                McpTraceEvent(
                    phase="initialize",
                    server_name=request.server_name,
                    tool_name=request.tool_name,
                    status="success",
                    duration_ms=protocol_call.initialize_ms,
                    detail=f"MCP Session 初始化完成，protocol={protocol_call.protocol_version}。",
                ),
                McpTraceEvent(
                    phase="tools/list",
                    server_name=request.server_name,
                    tool_name=request.tool_name,
                    status="success",
                    duration_ms=protocol_call.list_tools_ms,
                    detail="调用前已确认目标工具存在。",
                ),
                McpTraceEvent(
                    phase="tools/call",
                    server_name=request.server_name,
                    tool_name=request.tool_name,
                    status="failed" if result.isError else "success",
                    duration_ms=protocol_call.call_tool_ms,
                    detail="MCP Server 返回 Tool Error。" if result.isError else "MCP Server 返回调用结果。",
                ),
            ]
        )
        result_size = len(
            json.dumps(
                result.model_dump(mode="json", by_alias=True, exclude_none=True),
                ensure_ascii=False,
            ).encode("utf-8")
        )
        if result_size > self.max_result_bytes:
            message = f"MCP Tool 返回 {result_size} bytes，超过上限 {self.max_result_bytes} bytes。"
            trace.append(
                McpTraceEvent(
                    phase="adapt_result",
                    server_name=request.server_name,
                    tool_name=request.tool_name,
                    status="failed",
                    duration_ms=0,
                    detail=message,
                )
            )
            return McpToolCallResponse(
                server_name=request.server_name,
                tool_name=request.tool_name,
                namespaced_name=f"{request.server_name}::{request.tool_name}",
                status="failed",
                is_error=True,
                content=[],
                duration_ms=_elapsed_ms(started),
                error=message,
                trace=trace,
            )
        return McpToolCallResponse(
            server_name=request.server_name,
            tool_name=request.tool_name,
            namespaced_name=f"{request.server_name}::{request.tool_name}",
            status="failed" if result.isError else "success",
            is_error=bool(result.isError),
            content=adapt_content(result),
            structured_content=structured_content(result),
            duration_ms=_elapsed_ms(started),
            error=_tool_error_text(result) if result.isError else None,
            trace=trace,
        )


def _safe_error_message(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        messages = [_safe_error_message(child) for child in exc.exceptions]
        return "; ".join(dict.fromkeys(message for message in messages if message))
    if isinstance(exc, asyncio.TimeoutError):
        return "MCP Server 连接或调用超时。"
    message = str(exc).strip()
    return message or type(exc).__name__


def _tool_error_text(result) -> str:
    texts = [getattr(block, "text", "") for block in result.content]
    message = " ".join(text.strip() for text in texts if text and text.strip())
    return message or "MCP Tool 返回 isError=true。"


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
