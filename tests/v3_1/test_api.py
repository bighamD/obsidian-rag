from fastapi.testclient import TestClient

from obsidian_rag.v3_1.app import app
from obsidian_rag.v3_1.dependencies import get_agent_service
from obsidian_rag.v3_1.router.service import RouterDecision
from obsidian_rag.v3_1.schemas import AgentAskResponse, AgentTraceStep


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            question=request.question,
            answer="这个问题需要查询实时天气服务，本地知识库不能保证准确。",
            used_retrieval=False,
            sources=[],
            router=RouterDecision(
                action="no_search",
                intent="external_realtime",
                reason="问题需要实时天气信息。",
                direct_answer="这个问题需要查询实时天气服务，本地知识库不能保证准确。",
            ),
            trace=[
                AgentTraceStep(
                    step_type="router",
                    decision="no_search",
                    reason="问题需要实时天气信息。",
                    metadata={"intent": "external_realtime"},
                ),
                AgentTraceStep(step_type="answer", reason="按 router 决策直接回答。"),
            ],
        )


def test_v3_1_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.1"}


def test_v3_1_agent_ask_returns_router_decision_and_trace():
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
    assert payload["router"]["action"] == "no_search"
    assert payload["router"]["intent"] == "external_realtime"
    assert payload["trace"][0]["step_type"] == "router"
