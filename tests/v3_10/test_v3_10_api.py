from fastapi.testclient import TestClient

from obsidian_rag.v3_10.app import app
from obsidian_rag.v3_10.dependencies import get_run_store, get_runtime_service
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from tests.v3_9.helpers import FakeAgentService


def test_v3_10_api_returns_run_then_allows_it_to_be_queried():
    store = InMemoryRunStore()
    runtime = AgentRuntimeService(agent_service=FakeAgentService(), run_store=store)
    app.dependency_overrides[get_runtime_service] = lambda: runtime
    app.dependency_overrides[get_run_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post("/agent/ask", json={"question": "生鸡肉要不要洗？"})
        run_id = response.json()["run"]["run_id"]
        queried = client.get(f"/runs/{run_id}")
        recent = client.get("/runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "succeeded"
    assert payload["agent_response"]["answer"] == "不建议清洗生鸡肉，因为水花可能造成交叉污染。"
    assert queried.status_code == 200
    assert queried.json()["run_id"] == run_id
    assert recent.json()[0]["run_id"] == run_id


def test_v3_10_api_exposes_safe_runtime_config_and_health():
    client = TestClient(app)

    health = client.get("/health")
    config = client.get("/runtime/config")

    assert health.json() == {"status": "ok", "version": "v3.10"}
    assert config.status_code == 200
    assert config.json()["run_store"] == "InMemoryRunStore（进程重启后清空）"
