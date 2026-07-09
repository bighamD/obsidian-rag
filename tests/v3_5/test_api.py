from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_5.app import app
from obsidian_rag.v3_5.dependencies import get_agent_service
from obsidian_rag.v3_5.schemas import AgentAskResponse, AgentTraceStep, StepResult


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_test",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["KB-001：food.md"],
            plan=Plan(
                goal="生成并执行计划",
                steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")],
            ),
            step_results=[
                StepResult(
                    step_id="s1",
                    kind="search",
                    tool_name="search_notes",
                    query="生鸡肉 清洗",
                    status="success",
                    result_count=1,
                    sources=["KB-001：food.md"],
                )
            ],
            graph_path=["planner", "execute_steps", "synthesize_answer"],
            trace=[
                AgentTraceStep(
                    node_name="execute_steps",
                    step_type="tool_result",
                    step_id="s1",
                    tool_name="search_notes",
                    result_count=1,
                )
            ],
        )


def test_v3_5_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.5"}


def test_v3_5_agent_ask_returns_step_results():
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    try:
        response = client.post(
            "/agent/ask",
            json={"question": "生鸡肉需要清洗吗", "top_k": 5, "mode": "hybrid", "max_steps": 4},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run_test"
    assert payload["step_results"][0]["tool_name"] == "search_notes"
    assert payload["graph_path"] == ["planner", "execute_steps", "synthesize_answer"]
