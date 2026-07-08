from fastapi.testclient import TestClient

from obsidian_rag.llm import ToolCall
from obsidian_rag.v3_2.app import app
from obsidian_rag.v3_2.dependencies import get_agent_service
from obsidian_rag.v3_2.schemas import AgentAskResponse, AgentTraceStep


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            question=request.question,
            answer="这个问题需要查询实时天气服务。",
            used_retrieval=False,
            sources=[],
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="no_search",
                    arguments={"reason": "需要实时外部信息", "answer": "这个问题需要查询实时天气服务。"},
                )
            ],
            trace=[
                AgentTraceStep(
                    step_type="tool_selection",
                    tool_name="no_search",
                    reason="需要实时外部信息",
                    metadata={"arguments": {"reason": "需要实时外部信息"}},
                ),
                AgentTraceStep(step_type="answer", reason="按 no_search 工具结果直接回答。"),
            ],
        )


def test_v3_2_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.2"}


def test_v3_2_agent_ask_returns_tool_calls_and_trace():
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
    assert payload["used_retrieval"] is False
    assert payload["tool_calls"][0]["name"] == "no_search"
    assert payload["trace"][0]["step_type"] == "tool_selection"
