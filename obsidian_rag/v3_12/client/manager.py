from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Implementation, Tool


@dataclass(frozen=True)
class McpServerDefinition:
    """启动一个 stdio MCP Server 所需的内部配置。"""

    name: str
    description: str
    command: str
    args: tuple[str, ...]
    cwd: Path
    timeout_seconds: float = 15.0


@dataclass(frozen=True)
class McpDiscoveryResult:
    tools: list[Tool]
    initialize_ms: int
    list_tools_ms: int
    protocol_version: str


@dataclass(frozen=True)
class McpProtocolCallResult:
    tool: Tool
    result: CallToolResult
    initialize_ms: int
    list_tools_ms: int
    call_tool_ms: int
    protocol_version: str


class McpClientManager:
    """管理 MCP Server 配置，并为每次学习调用创建短生命周期 Session。"""

    def __init__(self, servers: list[McpServerDefinition]):
        self._servers = {server.name: server for server in servers}

    def list_servers(self) -> list[McpServerDefinition]:
        return list(self._servers.values())

    def get_server(self, name: str) -> McpServerDefinition:
        server = self._servers.get(name)
        if server is None:
            raise KeyError(f"未知 MCP Server: {name}")
        return server

    async def discover_tools(self, server_name: str) -> McpDiscoveryResult:
        server = self.get_server(server_name)
        async with asyncio.timeout(server.timeout_seconds):
            async with self._session(server) as (session, initialize_ms, protocol_version):
                started = perf_counter()
                result = await session.list_tools()
                return McpDiscoveryResult(
                    tools=list(result.tools),
                    initialize_ms=initialize_ms,
                    list_tools_ms=_elapsed_ms(started),
                    protocol_version=protocol_version,
                )

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> McpProtocolCallResult:
        server = self.get_server(server_name)
        async with asyncio.timeout(server.timeout_seconds):
            async with self._session(server) as (session, initialize_ms, protocol_version):
                list_started = perf_counter()
                listed = await session.list_tools()
                list_tools_ms = _elapsed_ms(list_started)
                tool = next((candidate for candidate in listed.tools if candidate.name == tool_name), None)
                if tool is None:
                    raise KeyError(f"MCP Server {server_name} 不存在工具: {tool_name}")
                call_started = perf_counter()
                result = await session.call_tool(tool_name, arguments=arguments)
                return McpProtocolCallResult(
                    tool=tool,
                    result=result,
                    initialize_ms=initialize_ms,
                    list_tools_ms=list_tools_ms,
                    call_tool_ms=_elapsed_ms(call_started),
                    protocol_version=protocol_version,
                )

    @asynccontextmanager
    async def _session(
        self,
        server: McpServerDefinition,
    ) -> AsyncIterator[tuple[ClientSession, int, str]]:
        parameters = StdioServerParameters(
            command=server.command,
            args=list(server.args),
            cwd=server.cwd,
            env=dict(os.environ),
        )
        initialize_started = perf_counter()
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=server.timeout_seconds),
                client_info=Implementation(name="obsidian-rag-v3.12", version="3.12"),
            ) as session:
                initialized = await session.initialize()
                yield session, _elapsed_ms(initialize_started), initialized.protocolVersion


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
