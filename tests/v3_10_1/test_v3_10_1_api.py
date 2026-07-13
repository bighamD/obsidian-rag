from fastapi.testclient import TestClient

from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store, get_runtime_service
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10_1.app import app
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from tests.v3_9.helpers import FakeAgentService


def test_v3_10_1_console_api_reads_memory_and_reuses_production_ask(tmp_path):
    memory_store = SQLiteConversationMemoryStore(tmp_path / "console-memory.sqlite3")
    memory_store.append_turn("conv_console", "第一轮问题", "第一轮回答", ["food.md"], [])
    run_store = InMemoryRunStore()
    runtime = AgentRuntimeService(agent_service=FakeAgentService(), run_store=run_store)
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_runtime_service] = lambda: runtime
    client = TestClient(app)
    try:
        conversation = client.get("/console/conversations/conv_console?window=3")
        asked = client.post("/agent/ask", json={"question": "生鸡肉要不要洗？", "conversation_id": "conv_console"})
    finally:
        app.dependency_overrides.clear()

    assert conversation.status_code == 200
    assert conversation.json()["memory_snapshot"]["recent_turns"][0]["user_message"] == "第一轮问题"
    assert asked.status_code == 200
    assert asked.json()["run"]["status"] == "succeeded"


def test_v3_10_1_console_config_and_health_are_json():
    client = TestClient(app)

    health = client.get("/health")
    config = client.get("/console/config")

    assert health.json() == {"status": "ok", "version": "v3.10.1"}
    assert config.json() == {
        "api_mode": "json",
        "streaming_available": False,
        "default_memory_window": 3,
    }
