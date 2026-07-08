from fastapi.testclient import TestClient

from obsidian_rag.llm import ToolCall
from obsidian_rag.v3_3.app import app
from obsidian_rag.v3_3.dependencies import get_agent_service
from obsidian_rag.v3_3.schemas import AgentAskResponse, AgentTraceStep


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            question=request.question,
            answer="请查看实时天气服务。",
            used_retrieval=False,
            sources=[],
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="no_search",
                    arguments={"reason": "需要实时天气。", "answer": "请查看实时天气服务。"},
                )
            ],
            graph_path=["select_tool", "no_search"],
            trace=[
                AgentTraceStep(
                    node_name="select_tool",
                    step_type="tool_selection",
                    tool_name="no_search",
                    reason="需要实时天气。",
                    metadata={"arguments": {"reason": "需要实时天气。"}},
                ),
                AgentTraceStep(node_name="no_search", step_type="answer", reason="no_search 节点直接返回。"),
            ],
        )


def test_v3_3_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.3"}


def test_v3_3_agent_ask_returns_graph_path_and_trace():
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    try:
        response = client.post(
            "/agent/ask",
            json={"question": "今天深圳天气怎么样", "top_k": 5, "mode": "hybrid", "max_steps": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_path"] == ["select_tool", "no_search"]
    assert payload["trace"][0]["node_name"] == "select_tool"
    assert payload["tool_calls"][0]["name"] == "no_search"

