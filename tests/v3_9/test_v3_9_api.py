from fastapi.testclient import TestClient

from obsidian_rag.v3_9.app import app
from obsidian_rag.v3_9.dependencies import get_agent_evaluator
from obsidian_rag.v3_9.evaluation.evaluator import AgentEvaluator
from tests.v3_9.helpers import FakeAgentService


def test_v3_9_agent_eval_api_returns_check_breakdown():
    app.dependency_overrides[get_agent_evaluator] = lambda: AgentEvaluator(FakeAgentService())
    client = TestClient(app)
    try:
        response = client.post(
            "/eval/agent",
            json={
                "id": "chicken-wash",
                "request": {"question": "生鸡肉要不要洗？"},
                "expect": {
                    "should_retrieve": True,
                    "expected_tools": ["search_notes"],
                    "expected_chunk_ids": ["KB-072"],
                    "expected_answer_points": ["不建议清洗生鸡肉", "交叉污染"],
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is True
    assert payload["score"] == 1.0
    assert [check["name"] for check in payload["checks"]] == [
        "routing",
        "tools",
        "retrieval_chunks",
        "answer",
    ]


def test_v3_9_agent_eval_dataset_api_returns_summary(tmp_path):
    dataset_path = tmp_path / "agent-eval.yaml"
    dataset_path.write_text(
        """cases:
  - id: chicken-wash
    request:
      question: 生鸡肉要不要洗？
    expect:
      should_retrieve: true
      expected_tools: [search_notes]
      expected_chunk_ids: [KB-072]
""",
        encoding="utf-8",
    )
    app.dependency_overrides[get_agent_evaluator] = lambda: AgentEvaluator(FakeAgentService())
    client = TestClient(app)
    try:
        response = client.post(
            "/eval/agent/dataset",
            json={"dataset_path": str(dataset_path), "save": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "case_count": 1,
        "passed_count": 1,
        "pass_rate": 1.0,
        "mean_score": 1.0,
    }
    assert payload["output_path"] is None
