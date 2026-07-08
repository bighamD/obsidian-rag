from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v2.app import app
from obsidian_rag.v2.dependencies import get_retrieval_service


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [
            SearchResult(
                chunk=TextChunk(text="不建议清洗生鸡肉。", metadata={"source": "food.md"}),
                score=0.8,
            )
        ]


def test_v2_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v2"}


def test_v2_eval_retrieval_returns_metrics_json(tmp_path: Path):
    dataset_path = tmp_path / "eval_set.yaml"
    dataset_path.write_text(
        """
examples:
  - id: chicken
    question: 鸡肉要洗吗
    expected_source_files:
      - food.md
""".strip(),
        encoding="utf-8",
    )
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrievalService()
    client = TestClient(app)

    try:
        response = client.post(
            "/eval/retrieval",
            json={"dataset_path": str(dataset_path), "top_k": 3, "mode": "hybrid", "save": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["example_count"] == 1
    assert payload["summary"]["hit_rate_at_k"] == 1.0
    assert payload["examples"][0]["id"] == "chicken"


def test_v2_eval_answer_returns_metrics_json():
    client = TestClient(app)

    response = client.post(
        "/eval/answer",
        json={
            "answer": "不建议冲洗生鸡肉，要避免交叉污染。",
            "expected_source_files": ["food.md"],
            "cited_source_files": ["food.md"],
            "expected_answer_points": ["不建议冲洗生鸡肉", "充分加热"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_coverage"] == 1.0
    assert payload["answer_point_coverage"] == 0.5
    assert payload["missing_answer_points"] == ["充分加热"]
