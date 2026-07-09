from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_6.app import app
from obsidian_rag.v3_6.dependencies import get_agent_service
from obsidian_rag.v3_6.schemas import (
    AgentAskResponse,
    AgentTraceStep,
    EvidenceCheckResult,
    StepResult,
)


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_test",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(goal="执行并检查证据", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")]),
            step_results=[
                StepResult(
                    step_id="s1",
                    kind="search",
                    tool_name="search_notes",
                    query="生鸡肉 清洗",
                    status="success",
                    result_count=1,
                    sources=["food.md"],
                )
            ],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(
                is_sufficient=True,
                missing_points=[],
                suggested_queries=[],
                checked_step_ids=["s1"],
                retry_count=0,
                reason="所有 search step 都有检索结果。",
            ),
            graph_path=["planner", "execute_steps", "evidence_check", "synthesize_answer"],
            trace=[
                AgentTraceStep(
                    node_name="evidence_check",
                    step_type="evidence_check",
                    reason="所有 search step 都有检索结果。",
                )
            ],
        )


def test_v3_6_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.6"}


def test_v3_6_agent_ask_returns_evidence_check():
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
    assert payload["evidence_check"]["is_sufficient"] is True
    assert payload["retry_step_results"] == []
    assert payload["graph_path"] == ["planner", "execute_steps", "evidence_check", "synthesize_answer"]
