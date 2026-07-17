from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncIterator, Literal

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation, Tool

from obsidian_rag.v3_12.client.adapter import adapt_content, adapt_tool, structured_content
from obsidian_rag.v3_12.schemas import McpToolCallResponse, McpTraceEvent
from obsidian_rag.v3_12_3.config import resolve_server_cwd
from obsidian_rag.v3_12_3.schemas import (
    McpRuntimeResponse,
    McpServerConfig,
    McpServerRegistryConfig,
    McpServerRuntime,
)


CommandKind = Literal["refresh", "reconnect", "call", "stop"]


@dataclass
class _ServerCommand:
    kind: CommandKind
    future: asyncio.Future
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0


@dataclass
class _ManagedServer:
    config: McpServerConfig
    status: str = "disconnected"
    tools: list[Tool] = field(default_factory=list)
    protocol_version: str | None = None
    connected_at: str | None = None
    discovered_at: str | None = None
    call_count: int = 0
    failure_count: int = 0
    last_error: str | None = None
    queue: asyncio.Queue[_ServerCommand] | None = None
    worker: asyncio.Task | None = None


class McpConnectionManager:
    """每个 Server 使用一个长期 Worker Task，安全持有并复用 MCP Session。"""

    def __init__(self, registry: McpServerRegistryConfig, registry_path: Path):
        self.registry = registry
        self.registry_path = registry_path
        self._servers = {
            config.name: _ManagedServer(config=config)
            for config in registry.servers
            if config.enabled
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lifecycle_lock = threading.RLock()

    @property
    def started(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._loop and self._loop.is_running())

    def start(self) -> None:
        with self._lifecycle_lock:
            if self.started:
                return
            self._ready.clear()
            self._thread = threading.Thread(target=self._run_loop, name="mcp-connection-manager", daemon=True)
            self._thread.start()
            if not self._ready.wait(timeout=5):
                raise RuntimeError("MCP Connection Manager 事件循环启动超时。")
            self._submit(self._start_workers(), timeout=5)

        startup_names = [
            server.config.name
            for server in self._servers.values()
            if server.config.connect_on_startup
        ]
        if startup_names:
            self._submit(self._refresh_many(startup_names, reconnect=False), timeout=_timeout_for(self._servers.values()))

    def stop(self) -> None:
        with self._lifecycle_lock:
            if not self.started or self._loop is None:
                return
            try:
                self._submit(self._stop_workers(), timeout=_timeout_for(self._servers.values()))
            finally:
                self._loop.call_soon_threadsafe(self._loop.stop)
                if self._thread:
                    self._thread.join(timeout=5)
                self._thread = None
                self._loop = None

    def refresh(self, server_name: str | None = None, *, reconnect: bool = False) -> McpRuntimeResponse:
        self._ensure_started()
        names = [server_name] if server_name else list(self._servers)
        for name in names:
            if name not in self._servers:
                raise KeyError(f"未知或未启用 MCP Server: {name}")
        self._submit(self._refresh_many(names, reconnect=reconnect), timeout=_timeout_for(self._servers.values()))
        return self.runtime()

    def runtime(self) -> McpRuntimeResponse:
        self._ensure_started()
        tools, errors = self.list_tools()
        return McpRuntimeResponse(
            registry_path=str(self.registry_path),
            started=self.started,
            servers=[_runtime_state(server) for server in self._servers.values()],
            tools=tools,
            errors=errors,
        )

    def list_tools(self) -> tuple[list, dict[str, str]]:
        self._ensure_started()
        self._submit(self._refresh_stale_servers(), timeout=_timeout_for(self._servers.values()))
        definitions = []
        errors: dict[str, str] = {}
        for server in self._servers.values():
            definitions.extend(adapt_tool(server.config.name, tool) for tool in server.tools)
            if server.last_error:
                errors[server.config.name] = server.last_error
        return definitions, errors

    def call_tool(self, namespaced_name: str, arguments: dict[str, Any]) -> McpToolCallResponse:
        self._ensure_started()
        if "::" not in namespaced_name:
            raise ValueError("MCP Tool 名称必须使用 server::tool 格式。")
        server_name, tool_name = namespaced_name.split("::", 1)
        server = self._servers.get(server_name)
        if server is None:
            raise KeyError(f"未知或未启用 MCP Server: {server_name}")
        return self._submit(
            self._send_command(server, "call", tool_name=tool_name, arguments=arguments),
            timeout=server.config.timeout_seconds * 2 + 5,
        )

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    def _ensure_started(self) -> None:
        if not self.started:
            self.start()

    def _submit(self, coroutine, *, timeout: float):
        if self._loop is None:
            raise RuntimeError("MCP Connection Manager 尚未启动。")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result(timeout=timeout)

    async def _start_workers(self) -> None:
        for server in self._servers.values():
            server.queue = asyncio.Queue()
            server.worker = asyncio.create_task(self._server_worker(server), name=f"mcp-server-{server.config.name}")

    async def _stop_workers(self) -> None:
        await asyncio.gather(
            *(self._send_command(server, "stop") for server in self._servers.values()),
            return_exceptions=True,
        )
        workers = [server.worker for server in self._servers.values() if server.worker is not None]
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    async def _refresh_many(self, names: list[str], *, reconnect: bool) -> None:
        kind: CommandKind = "reconnect" if reconnect else "refresh"
        await asyncio.gather(
            *(self._send_command(self._servers[name], kind) for name in names),
            return_exceptions=True,
        )

    async def _refresh_stale_servers(self) -> None:
        stale = [server for server in self._servers.values() if _cache_expired(server)]
        if stale:
            await asyncio.gather(
                *(self._send_command(server, "refresh") for server in stale),
                return_exceptions=True,
            )

    async def _send_command(
        self,
        server: _ManagedServer,
        kind: CommandKind,
        *,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ):
        if server.queue is None:
            raise RuntimeError(f"MCP Server Worker 未启动: {server.config.name}")
        future = asyncio.get_running_loop().create_future()
        await server.queue.put(
            _ServerCommand(
                kind=kind,
                future=future,
                tool_name=tool_name,
                arguments=arguments or {},
            )
        )
        return await future

    async def _server_worker(self, server: _ManagedServer) -> None:
        pending: _ServerCommand | None = None
        while True:
            command = pending or await server.queue.get()  # type: ignore[union-attr]
            pending = None
            if command.kind == "stop":
                _resolve_future(command.future, None)
                return
            try:
                async with self._open_session(server) as session:
                    while True:
                        if command.kind == "stop":
                            _resolve_future(command.future, None)
                            return
                        if command.kind == "reconnect":
                            command.kind = "refresh"
                            server.discovered_at = None
                            pending = command
                            break
                        if command.kind == "refresh":
                            await self._discover(server, session)
                            _resolve_future(command.future, True)
                        elif command.kind == "call":
                            try:
                                result = await self._call_in_session(server, session, command)
                            except Exception as exc:
                                if command.attempts < 1:
                                    command.attempts += 1
                                    pending = command
                                    self._mark_failure(server, exc)
                                    break
                                self._mark_failure(server, exc)
                                _resolve_future(command.future, _failed_call(server, command.tool_name or "", 0, exc))
                            else:
                                _resolve_future(command.future, result)
                        command = pending or await server.queue.get()  # type: ignore[union-attr]
                        pending = None
            except Exception as exc:
                self._mark_failure(server, exc)
                if command.kind == "call" and command.attempts < 1:
                    command.attempts += 1
                    pending = command
                elif command.kind == "call":
                    _resolve_future(command.future, _failed_call(server, command.tool_name or "", 0, exc))
                else:
                    _resolve_future(command.future, False)
                await asyncio.sleep(min(1.0, server.config.timeout_seconds / 10))

    @asynccontextmanager
    async def _open_session(self, server: _ManagedServer) -> AsyncIterator[ClientSession]:
        server.status = "connecting"
        server.last_error = None
        if server.config.transport == "stdio":
            parameters = StdioServerParameters(
                command=_resolve_command(server.config.command or "", self.registry_path),
                args=server.config.args,
                cwd=resolve_server_cwd(server.config.cwd, self.registry_path),
                env=dict(os.environ),
            )
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with self._client_session(server, read_stream, write_stream) as session:
                    yield session
        else:
            headers = _headers_from_environment(server.config)
            async with httpx.AsyncClient(headers=headers, timeout=server.config.timeout_seconds) as http_client:
                async with streamable_http_client(
                    server.config.url or "",
                    http_client=http_client,
                    terminate_on_close=False,
                ) as (read_stream, write_stream, _):
                    async with self._client_session(server, read_stream, write_stream) as session:
                        yield session
        server.status = "disconnected"

    @asynccontextmanager
    async def _client_session(self, server: _ManagedServer, read_stream, write_stream) -> AsyncIterator[ClientSession]:
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=server.config.timeout_seconds),
            client_info=Implementation(name="obsidian-rag-v3.12.3", version="3.12.3"),
        ) as session:
            initialized = await session.initialize()
            server.protocol_version = initialized.protocolVersion
            server.connected_at = _now()
            server.status = "connected"
            await self._discover(server, session)
            yield session

    async def _discover(self, server: _ManagedServer, session: ClientSession) -> None:
        listed = await session.list_tools()
        allowlist = set(server.config.tool_allowlist)
        server.tools = [tool for tool in listed.tools if tool.name in allowlist]
        server.discovered_at = _now()
        server.status = "connected"
        server.last_error = None

    async def _call_in_session(
        self,
        server: _ManagedServer,
        session: ClientSession,
        command: _ServerCommand,
    ) -> McpToolCallResponse:
        tool_name = command.tool_name or ""
        if tool_name not in {tool.name for tool in server.tools}:
            raise KeyError(f"MCP Tool 未在 allowlist 或 tools/list 中: {server.config.name}::{tool_name}")
        started = perf_counter()
        result = await session.call_tool(tool_name, arguments=command.arguments)
        server.call_count += 1
        result_size = len(
            json.dumps(
                result.model_dump(mode="json", by_alias=True, exclude_none=True),
                ensure_ascii=False,
            ).encode("utf-8")
        )
        if result_size > self.registry.max_result_bytes:
            raise ValueError(
                f"MCP Tool 返回 {result_size} bytes，超过上限 {self.registry.max_result_bytes} bytes。"
            )
        return McpToolCallResponse(
            server_name=server.config.name,
            tool_name=tool_name,
            namespaced_name=f"{server.config.name}::{tool_name}",
            status="failed" if result.isError else "success",
            is_error=bool(result.isError),
            content=adapt_content(result),
            structured_content=structured_content(result),
            duration_ms=_elapsed_ms(started),
            error=_tool_error(result) if result.isError else None,
            trace=[
                McpTraceEvent(
                    phase="session_reused",
                    server_name=server.config.name,
                    tool_name=tool_name,
                    status="success",
                    duration_ms=0,
                    detail=f"复用 {server.config.transport} MCP Session。",
                ),
                McpTraceEvent(
                    phase="tools/call",
                    server_name=server.config.name,
                    tool_name=tool_name,
                    status="failed" if result.isError else "success",
                    duration_ms=_elapsed_ms(started),
                    detail="MCP Tool 返回错误。" if result.isError else "MCP Tool 调用完成。",
                ),
            ],
        )

    def _mark_failure(self, server: _ManagedServer, exc: BaseException) -> None:
        server.failure_count += 1
        server.last_error = _safe_error(exc)
        server.status = "degraded" if server.connected_at else "failed"


def _runtime_state(server: _ManagedServer) -> McpServerRuntime:
    return McpServerRuntime(
        name=server.config.name,
        description=server.config.description,
        transport=server.config.transport,
        status=server.status,
        protocol_version=server.protocol_version,
        tool_count=len(server.tools),
        tool_names=[tool.name for tool in server.tools],
        connected_at=server.connected_at,
        discovered_at=server.discovered_at,
        call_count=server.call_count,
        failure_count=server.failure_count,
        last_error=server.last_error,
    )


def _failed_call(
    server: _ManagedServer,
    tool_name: str,
    started: float,
    exc: BaseException,
) -> McpToolCallResponse:
    message = _safe_error(exc)
    return McpToolCallResponse(
        server_name=server.config.name,
        tool_name=tool_name,
        namespaced_name=f"{server.config.name}::{tool_name}",
        status="failed",
        is_error=True,
        content=[],
        duration_ms=_elapsed_ms(started) if started else 0,
        error=message,
        trace=[
            McpTraceEvent(
                phase="tools/call",
                server_name=server.config.name,
                tool_name=tool_name,
                status="failed",
                duration_ms=_elapsed_ms(started) if started else 0,
                detail=message,
            )
        ],
    )


def _resolve_future(future: asyncio.Future, value: Any) -> None:
    if not future.done():
        future.set_result(value)


def _headers_from_environment(config: McpServerConfig) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header, env_name in config.headers_from_env.items():
        value = os.getenv(env_name)
        if not value:
            raise ValueError(f"MCP Server {config.name} 缺少认证环境变量: {env_name}")
        headers[header] = value
    return headers


def _resolve_command(command: str, registry_path: Path) -> str:
    path = Path(command).expanduser()
    if path.is_absolute() or "/" not in command:
        return str(path)
    return os.path.abspath(registry_path.parent / path)


def _cache_expired(server: _ManagedServer) -> bool:
    if not server.discovered_at:
        return True
    discovered = datetime.fromisoformat(server.discovered_at)
    return datetime.now(timezone.utc) - discovered >= timedelta(seconds=server.config.tool_cache_ttl_seconds)


def _timeout_for(servers) -> float:
    values = [server.config.timeout_seconds for server in servers]
    return max(values, default=15) + 10


def _tool_error(result) -> str:
    texts = [getattr(block, "text", "") for block in result.content]
    return " ".join(text.strip() for text in texts if text and text.strip()) or "MCP Tool 返回 isError=true。"


def _safe_error(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        messages = [_safe_error(item) for item in exc.exceptions]
        return "; ".join(dict.fromkeys(message for message in messages if message))
    message = str(exc).strip()
    return message or type(exc).__name__


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
