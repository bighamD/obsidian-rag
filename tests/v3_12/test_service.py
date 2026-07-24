import asyncio
from pathlib import Path

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from obsidian_rag.v3_12.client.manager import (
    McpDiscoveryResult,
    McpProtocolCallResult,
    McpServerDefinition,
)
from obsidian_rag.v3_12.schemas import McpCallRequest
from obsidian_rag.v3_12.service import McpIntegrationService


class FakeManager:
    def __init__(self):
        self.server = McpServerDefinition(
            name="demo",
            description="fake",
            command="python",
            args=("server.py",),
            cwd=Path("."),
        )
        self.tool = Tool(
            name="echo",
            description="Echo text",
            inputSchema={"type": "object", "properties": {"text": {"type": "string"}}},
            annotations=ToolAnnotations(readOnlyHint=True),
        )

    def list_servers(self):
        return [self.server]

    def get_server(self, name):
        if name != "demo":
            raise KeyError(name)
        return self.server

    async def discover_tools(self, server_name):
        return McpDiscoveryResult([self.tool], 5, 2, "test")

    async def call_tool(self, server_name, tool_name, arguments):
        return McpProtocolCallResult(
            tool=self.tool,
            result=CallToolResult(
                content=[TextContent(type="text", text=arguments["text"])],
                structuredContent={"echo": arguments["text"]},
            ),
            initialize_ms=5,
            list_tools_ms=2,
            call_tool_ms=3,
            protocol_version="test",
        )


def test_lists_and_adapts_mcp_tools():
    response = asyncio.run(McpIntegrationService(FakeManager()).list_tools("demo"))  # type: ignore[arg-type]

    assert response.tools[0].namespaced_name == "demo::echo"
    assert response.tools[0].read_only is True
    assert [event.phase for event in response.trace] == ["initialize", "tools/list"]


def test_calls_and_adapts_mcp_result():
    response = asyncio.run(
        McpIntegrationService(FakeManager()).call_tool(  # type: ignore[arg-type]
            McpCallRequest(server_name="demo", tool_name="echo", arguments={"text": "hello"})
        )
    )

    assert response.status == "success"
    assert response.structured_content == {"echo": "hello"}
    assert response.content[0].payload["text"] == "hello"
