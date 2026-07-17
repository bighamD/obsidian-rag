from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag.config import RagConfig
from obsidian_rag.reranking.providers import FakeReranker
from obsidian_rag.reranking.retrieval import RerankingRetrievalService
from obsidian_rag.reranking.service import RerankingService
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_12_2.app import app
from obsidian_rag.v3_12_2.dependencies import get_learning_service
from obsidian_rag.v3_12_2.service import RerankerLearningService


class BaseRetrieval:
    def search(self, query, top_k, mode, filters=None, collection=None):
        return [
            SearchResult(
                TextChunk(
                    "parent answer",
                    {
                        "source": "food.md",
                        "parent_id": "p1",
                        "matched_child_text": "剩菜冷藏三到四天",
                        "returned_parent_text": "parent answer",
                    },
                ),
                0.8,
            )
        ]

    def collection_name(self, collection=None):
        return collection or "food_safety"


def _learning_service(runtime=None) -> RerankerLearningService:
    config = RagConfig(
        api_key="",
        base_url="http://example.test/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=3,
        embedding_provider="hash",
        ollama_base_url="http://localhost",
        qdrant_url=None,
        db_path=Path(".rag/test"),
        collection_name="food_safety",
        min_score=0.0,
        vault_path=None,
        rerank_enabled=True,
        rerank_provider="fake",
        rerank_candidates=5,
        rerank_top_k=5,
    )
    reranker = RerankingService(
        FakeReranker(lambda _q, _text: 1),
        enabled=True,
        provider="fake",
        model="fake",
        device="cpu",
        timeout_seconds=1,
    )
    return RerankerLearningService(config, RerankingRetrievalService(BaseRetrieval(), reranker, config), runtime)


def test_health_and_rerank_search_api():
    app.dependency_overrides[get_learning_service] = _learning_service
    try:
        client = TestClient(app)
        assert client.get("/health").json()["version"] == "v3.12.2"
        response = client.post("/rerank/search", json={"query": "剩菜多久", "collection": "food_safety"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["run"]["provider"] == "fake"
        assert payload["results"][0]["parent_id"] == "p1"
    finally:
        app.dependency_overrides.clear()


def test_cli_dispatches_v3_12_2_rerank(monkeypatch):
    import obsidian_rag.cli as cli

    captured = {}
    monkeypatch.setattr(cli, "run_agent3122_rerank", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(sys, "argv", ["obsidian-rag", "agent-v3-12-2", "rerank", "剩菜多久"])

    cli.main()

    assert captured["query"] == "剩菜多久"
    assert captured["api_base"] == "http://127.0.0.1:8021"


def test_agent_sse_route_uses_v3_12_2_runtime():
    class FakeRuntime:
        def start_stream(self, request):
            return "run_test"

        def stream(self, run_id):
            assert run_id == "run_test"
            yield 'event: run_succeeded\ndata: {"name":"run_succeeded"}\n\n'

    app.dependency_overrides[get_learning_service] = lambda: _learning_service(FakeRuntime())
    try:
        client = TestClient(app)
        response = client.post("/agent/ask/stream", json={"question": "剩菜多久"})
        assert response.status_code == 200
        assert "run_succeeded" in response.text
    finally:
        app.dependency_overrides.clear()
