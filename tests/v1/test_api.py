from fastapi.testclient import TestClient

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v1.app import app
from obsidian_rag.v1.dependencies import get_retrieval_service


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [
            SearchResult(
                chunk=TextChunk(
                    text="不建议清洗生鸡肉，直接充分加热更安全。",
                    metadata={
                        "source": "food.md",
                        "chunk_id": "KB-072",
                        "topic": "不建议清洗生鸡肉",
                    },
                ),
                score=0.87,
            )
        ]

    def compare_search(self, query, top_k=5, filters=None):
        results = self.search(query, top_k=top_k, mode="hybrid", filters=filters)
        return {"dense": results, "keyword": results, "hybrid": results}


def test_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v1"}


def test_search_returns_json_results():
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrievalService()
    client = TestClient(app)

    try:
        response = client.post(
            "/search",
            json={"query": "生鸡肉要不要洗", "top_k": 5, "mode": "hybrid"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "生鸡肉要不要洗"
    assert payload["mode"] == "hybrid"
    assert payload["results"][0]["chunk_id"] == "KB-072"
    assert payload["results"][0]["source"] == "food.md"
    assert payload["results"][0]["text_preview"] == "不建议清洗生鸡肉，直接充分加热更安全。"


def test_compare_search_returns_dense_keyword_and_hybrid_json():
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrievalService()
    client = TestClient(app)

    try:
        response = client.post("/compare-search", json={"query": "KB-072", "top_k": 3})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["results"]) == {"dense", "keyword", "hybrid"}
    assert payload["results"]["hybrid"][0]["chunk_id"] == "KB-072"
