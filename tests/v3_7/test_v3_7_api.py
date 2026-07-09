from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_7.app import app
from obsidian_rag.v3_7.dependencies import get_agent_service
from obsidian_rag.v3_7.schemas import (
    AgentAskResponse,
    AgentTraceStep,
    ContextBundle,
    ContextChunk,
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
            plan=Plan(goal="构建上下文并回答", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")]),
            step_results=[StepResult(step_id="s1", kind="search", tool_name="search_notes", query="生鸡肉 清洗", status="success", result_count=1)],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(is_sufficient=True, checked_step_ids=["s1"], reason="有证据。"),
            context_bundle=ContextBundle(
                messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
                included_chunks=[ContextChunk(step_id="s1", chunk_id="KB-072", source="food.md", score=0.88, text_preview="证据")],
                excluded_chunks=[],
                token_budget=4000,
                context_summary="已选择 1 个 chunks，排除 0 个 chunks。",
            ),
            graph_path=["planner", "execute_steps", "evidence_check", "build_context", "synthesize_answer"],
            trace=[AgentTraceStep(node_name="build_context", step_type="context", reason="构建 ContextBundle。")],
        )


def test_v3_7_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.7"}


def test_v3_7_agent_ask_returns_context_bundle():
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    try:
        response = client.post(
            "/agent/ask",
            json={"question": "生鸡肉需要清洗吗", "top_k": 5, "mode": "hybrid", "context_max_chunks": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_bundle"]["included_chunks"][0]["chunk_id"] == "KB-072"
    assert payload["context_bundle"]["context_summary"] == "已选择 1 个 chunks，排除 0 个 chunks。"
    assert payload["graph_path"] == ["planner", "execute_steps", "evidence_check", "build_context", "synthesize_answer"]
