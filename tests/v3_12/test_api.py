from fastapi.testclient import TestClient

from obsidian_rag.v3_12.app import app
from obsidian_rag.v3_12.dependencies import get_mcp_service
from obsidian_rag.v3_12.schemas import McpToolCallResponse, McpToolListResponse


class FakeService:
    def list_servers(self):
        return []

    async def list_tools(self, server_name=None):
        return McpToolListResponse(
            requested_server=server_name,
            tools=[],
            errors={},
            duration_ms=1,
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
            structured_content={"ok": True},
            duration_ms=1,
            trace=[],
        )


def test_swagger_mcp_call_surface():
    app.dependency_overrides[get_mcp_service] = lambda: FakeService()
    try:
        response = TestClient(app).post(
            "/mcp/call",
            json={"server_name": "demo", "tool_name": "echo", "arguments": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["structured_content"] == {"ok": True}
