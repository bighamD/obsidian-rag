import json

from fastapi.testclient import TestClient

from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8_1.schemas import (
    ContextBundle,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
)
from obsidian_rag.v3_10_3.app import app
from obsidian_rag.v3_10_3.dependencies import get_advanced_agent_service, get_runtime_service
from obsidian_rag.v3_10_3.schemas import (
    AdvancedAskResponse,
    StateHistoryEntry,
    StateHistoryResponse,
)


def _response(question: str = "生鸡肉要不要洗？") -> AdvancedAskResponse:
    return AdvancedAskResponse(
        run_id="adv_test",
        thread_id="thread_test",
        conversation_id="conv_test",
        question=question,
        answer="不建议清洗生鸡肉。",
        used_retrieval=True,
        sources=["food.md"],
        plan=Plan(goal="回答食品安全问题", steps=[PlanStep(id="s1", kind="search", query=question)]),
        planner_subgraph_path=["prepare_planner_input", "call_planner"],
        graph_path=["load_memory", "planner_subgraph", "answer", "save_memory"],
        step_results=[],
        retry_step_results=[],
        evidence_check=EvidenceCheckResult(is_sufficient=True, reason="证据充分。"),
        context_bundle=ContextBundle(
            messages=[],
            token_budget=4000,
            context_summary="测试上下文。",
        ),
        memory_snapshot=MemorySnapshot(conversation_id="conv_test", window=3),
        memory_compaction=MemoryCompactionResult(conversation_id="conv_test", reason="无需压缩。"),
        memory_write=MemoryWriteResult(conversation_id="conv_test", turn_id="turn_test", saved=True),
        trace=[],
        route_decisions=[],
        node_retry_counts={},
        parallel_task_count=1,
        state_history_count=3,
        stream_modes=["updates", "messages", "custom"],
    )


class FakeRuntimeService:
    def __init__(self):
        self.requests = []

    def ask(self, request):
        self.requests.append(request)
        return _response(request.question)

    def start_stream(self, request):
        self.requests.append(request)
        return "adv_stream"

    def stream(self, run_id):
        payload = {
            "event_id": 1,
            "run_id": run_id,
            "name": "run_succeeded",
            "status": "succeeded",
            "occurred_at": "2026-07-14T00:00:00Z",
            "detail": "完成。",
            "data": {"response": _response().model_dump(mode="json")},
        }
        yield f"event: run_succeeded\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class FakeAdvancedAgentService:
    def get_history(self, thread_id: str, limit: int = 20):
        return StateHistoryResponse(
            thread_id=thread_id,
            entries=[StateHistoryEntry(checkpoint_id="cp_1", next_nodes=["answer"], state_keys=["plan"])][:limit],
        )


def test_advanced_json_stream_history_and_config_endpoints():
    runtime = FakeRuntimeService()
    app.dependency_overrides[get_runtime_service] = lambda: runtime
    app.dependency_overrides[get_advanced_agent_service] = lambda: FakeAdvancedAgentService()
    client = TestClient(app)
    try:
        asked = client.post(
            "/advanced/ask",
            json={"question": "生鸡肉要不要洗？", "thread_id": "thread_test"},
        )
        streamed = client.post(
            "/advanced/ask/stream",
            json={"question": "生鸡肉要不要洗？", "thread_id": "thread_test"},
        )
        history = client.get("/advanced/history/thread_test?limit=1")
        config = client.get("/advanced/config")
        health = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert asked.status_code == 200
    assert asked.json()["thread_id"] == "thread_test"
    assert asked.json()["answer"] == "不建议清洗生鸡肉。"
    assert streamed.status_code == 200
    assert "event: run_succeeded" in streamed.text
    assert history.json()["entries"][0]["checkpoint_id"] == "cp_1"
    assert config.json()["stream_modes"] == ["updates", "messages", "custom"]
    assert health.json() == {"status": "ok", "version": "v3.10.3"}
