from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8.app import app
from obsidian_rag.v3_8.dependencies import get_agent_service, get_memory_store
from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_8.schemas import (
    AgentAskResponse,
    ContextBundle,
    EvidenceCheckResult,
    MemorySnapshot,
    MemoryWriteResult,
    StepResult,
)


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_test",
            conversation_id=request.conversation_id or "conv_test",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(goal="回答问题", steps=[PlanStep(id="s1", kind="search", query="厨房 清洁")]),
            step_results=[StepResult(step_id="s1", kind="search", status="success", result_count=1)],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(is_sufficient=True, reason="有证据。"),
            context_bundle=ContextBundle(
                messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
                token_budget=4000,
                context_summary="已构建上下文。",
            ),
            memory_snapshot=MemorySnapshot(conversation_id="conv_test", window=3),
            memory_write=MemoryWriteResult(conversation_id="conv_test", turn_id="turn_test", saved=True),
            graph_path=["load_memory", "planner", "build_context", "synthesize_answer", "save_memory"],
            trace=[],
        )


def test_v3_8_health_returns_json_status():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.8"}


def test_v3_8_agent_ask_returns_conversation_memory():
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)
    try:
        response = client.post(
            "/agent/ask",
            json={"question": "那厨房怎么清洁？", "conversation_id": "conv_test", "memory_window": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == "conv_test"
    assert payload["memory_snapshot"]["window"] == 3
    assert payload["memory_write"]["saved"] is True


def test_v3_8_memory_route_returns_saved_turns(tmp_path):
    memory_store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    memory_store.append_turn("conv_test", "第一轮问题", "第一轮回答", ["KB-001"], [])
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    client = TestClient(app)

    try:
        response = client.get("/memory/conv_test?window=3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_turn_count"] == 1
    assert payload["recent_turns"][0]["user_message"] == "第一轮问题"
