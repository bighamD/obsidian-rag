from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8_1.app import app
from obsidian_rag.v3_8_1.compaction import ConversationCompactor
from obsidian_rag.v3_8_1.dependencies import get_agent_service, get_memory_compactor, get_memory_store
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_8_1.schemas import (
    AgentAskResponse,
    ContextBundle,
    EvidenceCheckResult,
    MemorySnapshot,
    MemoryCompactionResult,
    MemoryWriteResult,
    StepResult,
)


class FakeAgentService:
    def __init__(self):
        self.requests = []

    def ask(self, request):
        self.requests.append(request)
        return AgentAskResponse(
            run_id="run_test",
            conversation_id=request.conversation_id or "conv_test",
            question=request.question,
            collection=request.collection or "obsidian_notes",
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
            memory_compaction=MemoryCompactionResult(
                conversation_id="conv_test",
                reason="未达到压缩阈值。",
            ),
            memory_write=MemoryWriteResult(conversation_id="conv_test", turn_id="turn_test", saved=True),
            graph_path=["load_memory", "compact_memory", "planner", "build_context", "synthesize_answer", "save_memory"],
            trace=[],
        )


class FakeSummaryClient:
    def complete(self, messages):
        return "此前讨论了生鸡肉处理。"


def test_v3_8_1_health_returns_json_status():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.8.1"}


def test_v3_8_1_agent_ask_returns_conversation_memory():
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
    assert payload["memory_compaction"]["compacted"] is False


def test_v3_8_1_agent_api_forwards_collection():
    service = FakeAgentService()
    app.dependency_overrides[get_agent_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post("/agent/ask", json={"question": "番茄意面怎么做？", "collection": "recipes"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.requests[0].collection == "recipes"
    assert response.json()["collection"] == "recipes"


def test_v3_8_1_memory_route_returns_saved_turns(tmp_path):
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


def test_v3_8_1_memory_compact_route_returns_summary(tmp_path):
    memory_store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    for index in range(1, 5):
        memory_store.append_turn("conv_test", f"问题 {index}", f"回答 {index}", [], [])
    compactor = ConversationCompactor(memory_store=memory_store, chat_client=FakeSummaryClient())
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_memory_compactor] = lambda: compactor
    client = TestClient(app)

    try:
        response = client.post(
            "/memory/conv_test/compact",
            json={
                "keep_recent_turns": 2,
                "trigger_turns": 99,
                "trigger_tokens": 50000,
                "force": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["compaction"]["compacted"] is True
    assert payload["compaction"]["summarized_turn_count"] == 2
    assert payload["memory_snapshot"]["summary_text"] == "此前讨论了生鸡肉处理。"
