import asyncio
import sys

from fastapi.testclient import TestClient

from obsidian_rag import cli
from obsidian_rag.v3_12_1.app import app
from obsidian_rag.v3_12_1.routes.agent import get_learning_service
from obsidian_rag.v3_12_1.schemas import (
    CoreStreamConfigResponse,
    UnifiedToolCallRequest,
)
from obsidian_rag.v3_12_1.tool_adapter import UnifiedToolService
from obsidian_rag.v3_12.schemas import McpToolCallResponse, McpToolDefinition, McpToolListResponse


class FakeLearningService:
    def config(self):
        return CoreStreamConfigResponse(
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            answer_delta_enabled=True,
            hidden_reasoning_exposed=False,
        )


class FakeRetrieval:
    def search(self, query, top_k=5, mode="hybrid", filters=None, collection=None):
        return []


class FakeMcpService:
    async def list_tools(self):
        return McpToolListResponse(
            tools=[
                McpToolDefinition(
                    server_name="demo",
                    name="get_server_time",
                    namespaced_name="demo::get_server_time",
                    description="读取服务时间",
                    input_schema={"type": "object"},
                    read_only=True,
                )
            ],
            errors={},
            duration_ms=0,
            trace=[],
        )

    async def call_tool(self, request):
        return McpToolCallResponse(
            server_name=request.server_name,
            tool_name=request.tool_name,
            namespaced_name=f"{request.server_name}::{request.tool_name}",
            status="success",
            is_error=False,
            content=[],
            structured_content={"time": "12:00"},
            duration_ms=1,
            trace=[],
        )


def test_v3_12_1_health_and_stream_config():
    app.dependency_overrides[get_learning_service] = lambda: FakeLearningService()
    try:
        client = TestClient(app)
        health = client.get("/health")
        config = client.get("/agent/stream/config")
    finally:
        app.dependency_overrides.clear()

    assert health.status_code == 200
    assert health.json()["version"] == "v3.12.1"
    assert config.json()["answer_delta_enabled"] is True
    assert config.json()["hidden_reasoning_exposed"] is False


def test_unified_registry_lists_local_tool_and_rejects_unknown():
    service = UnifiedToolService(FakeRetrieval(), FakeMcpService())

    tools = asyncio.run(service.list_tools())
    result = asyncio.run(service.call(UnifiedToolCallRequest(name="unknown", arguments={})))
    mcp_result = asyncio.run(
        service.call(UnifiedToolCallRequest(name="demo::get_server_time", arguments={}))
    )

    assert [item.name for item in tools.tools] == ["demo::get_server_time", "search_notes"]
    assert result.status == "failed"
    assert "Unknown tool" in (result.error or "")
    assert mcp_result.status == "success"
    assert mcp_result.data["structured_content"] == {"time": "12:00"}


def test_cli_main_parses_v3_12_1_stream_and_json(monkeypatch):
    captured = []
    monkeypatch.setattr(cli, "load_config", lambda: object())
    monkeypatch.setattr(cli, "run_agent3121_ask", lambda **kwargs: captured.append(kwargs))

    for argv in (
        ["obsidian-rag", "agent-v3-12-1", "ask", "剩菜可以保存多久？"],
        ["obsidian-rag", "agent-v3-12-1", "ask", "剩菜可以保存多久？", "--json"],
    ):
        monkeypatch.setattr(sys, "argv", argv)
        cli.main()

    assert captured[0]["stream"] is True
    assert captured[0]["api_base"] == "http://127.0.0.1:8020"
    assert captured[1]["stream"] is False
