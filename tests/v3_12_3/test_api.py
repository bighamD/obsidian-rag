from fastapi.testclient import TestClient

from obsidian_rag.v3_12.schemas import McpToolCallResponse
from obsidian_rag.v3_12_3.app import app
from obsidian_rag.v3_12_3.dependencies import get_integration_service
from obsidian_rag.v3_12_3.schemas import (
    McpExplicitToolCallResponse,
    McpRuntimeResponse,
)


class FakeService:
    def mcp_runtime(self):
        return McpRuntimeResponse(registry_path="mcp_servers.yaml", started=True, servers=[], tools=[], errors={})

    def call_tool(self, request):
        return McpExplicitToolCallResponse(
            name=request.name,
            result=McpToolCallResponse(
                server_name="demo",
                tool_name="get_server_time",
                namespaced_name=request.name,
                status="success",
                is_error=False,
                content=[],
                structured_content={"timezone": "Asia/Shanghai"},
                duration_ms=1,
                trace=[],
            ),
        )


def test_mcp_runtime_and_explicit_call_routes():
    app.dependency_overrides[get_integration_service] = lambda: FakeService()
    try:
        client = TestClient(app)
        runtime = client.get("/mcp/runtime")
        called = client.post(
            "/mcp/call",
            json={"name": "demo::get_server_time", "arguments": {"timezone": "Asia/Shanghai"}},
        )
    finally:
        app.dependency_overrides.clear()

    assert runtime.status_code == 200
    assert called.status_code == 200
    assert called.json()["result"]["status"] == "success"
