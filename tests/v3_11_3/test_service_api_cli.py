import sys
from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag import cli
from obsidian_rag.cli import run_collections3113
from obsidian_rag.config import RagConfig
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_11_3.app import app
from obsidian_rag.v3_11_3.dependencies import get_collection_router_service
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry
from obsidian_rag.v3_11_3.schemas import CollectionRouteRequest, CollectionSearchRequest, CollectionSelection
from obsidian_rag.v3_11_3.service import CollectionRouterService


def _config(tmp_path: Path) -> RagConfig:
    return RagConfig(
        api_key="test",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=8,
        embedding_provider="hash",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=tmp_path / "qdrant",
        collection_name="food_safety",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.0,
        vault_path=None,
    )


def _registry(tmp_path: Path) -> KnowledgeBaseRegistry:
    path = tmp_path / "knowledge_bases.yaml"
    path.write_text(
        """knowledge_bases:
  - id: food_safety
    collection: food_safety
    description: 食品安全
  - id: recipes
    collection: recipes
    description: 菜谱
""",
        encoding="utf-8",
    )
    registry = KnowledgeBaseRegistry(path)
    registry.load()
    return registry


class FailingRouter:
    def route(self, question, candidates, max_collections):
        raise AssertionError("显式 collection 不应调用 Router")


class MultiRouter:
    def route(self, question, candidates, max_collections):
        return CollectionSelection(
            status="multi_selected",
            selected_ids=["recipes", "food_safety"],
            selected_collections=["recipes", "food_safety"],
            reason="问题同时涉及菜谱和安全。",
            confidence=0.91,
            candidate_ids=[item.id for item in candidates],
        )


class CapturingRetrievalService:
    def __init__(self):
        self.collections = []

    def search(self, query, top_k=5, mode="hybrid", collection=None):
        self.collections.append(collection)
        return [
            SearchResult(
                chunk=TextChunk(text=f"{collection} evidence", metadata={"source": f"{collection}.md"}),
                score=0.8,
            )
        ]


def test_service_explicit_collection_skips_router(tmp_path: Path):
    retrieval = CapturingRetrievalService()
    service = CollectionRouterService(_config(tmp_path), _registry(tmp_path), retrieval, FailingRouter())

    response = service.search(CollectionSearchRequest(question="番茄炒蛋", collection="recipes"))

    assert response.selection.status == "explicit"
    assert retrieval.collections == ["recipes"]
    assert response.results[0].collection == "recipes"


def test_service_routes_and_searches_two_collections(tmp_path: Path):
    retrieval = CapturingRetrievalService()
    service = CollectionRouterService(_config(tmp_path), _registry(tmp_path), retrieval, MultiRouter())

    response = service.search(CollectionSearchRequest(question="鸡肉怎么做更安全？", top_k=3))

    assert response.selection.status == "multi_selected"
    assert set(retrieval.collections) == {"recipes", "food_safety"}
    assert len(response.results) == 2


def test_api_and_cli_return_collection_router_json(tmp_path: Path, capsys):
    service = CollectionRouterService(
        _config(tmp_path),
        _registry(tmp_path),
        CapturingRetrievalService(),
        FailingRouter(),
    )
    app.dependency_overrides[get_collection_router_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/collections/search",
            json={"question": "番茄炒蛋", "collection": "recipes"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["selection"]["status"] == "explicit"
    assert response.json()["results"][0]["collection"] == "recipes"

    run_collections3113(
        "route",
        _config(tmp_path),
        question="番茄炒蛋",
        collection="recipes",
        service=service,
    )
    assert '"status": "explicit"' in capsys.readouterr().out


def test_service_disabled_router_uses_default_collection(tmp_path: Path):
    service = CollectionRouterService(
        _config(tmp_path),
        _registry(tmp_path),
        CapturingRetrievalService(),
        FailingRouter(),
    )

    response = service.route(CollectionRouteRequest(question="食品安全", router_enabled=False))

    assert response.selection.status == "disabled"
    assert response.selection.selected_collections == ["food_safety"]


def test_service_rejects_unknown_explicit_collection(tmp_path: Path):
    retrieval = CapturingRetrievalService()
    service = CollectionRouterService(_config(tmp_path), _registry(tmp_path), retrieval, FailingRouter())

    response = service.search(CollectionSearchRequest(question="问题", collection="unknown"))

    assert response.selection.status == "invalid_selection"
    assert response.results == []
    assert retrieval.collections == []


def test_cli_main_parses_list_explicit_route_and_auto_search(monkeypatch, tmp_path: Path):
    config = _config(tmp_path)
    captured = []
    registry_path = tmp_path / "knowledge_bases.yaml"

    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "run_collections3113", lambda **kwargs: captured.append(kwargs))

    commands = [
        ["obsidian-rag", "collections-v3-11-3", "list", "--registry", str(registry_path)],
        [
            "obsidian-rag",
            "collections-v3-11-3",
            "route",
            "番茄炒蛋怎么做？",
            "--collection",
            "recipes",
        ],
        [
            "obsidian-rag",
            "collections-v3-11-3",
            "search",
            "鸡肉怎么做更安全？",
            "--max-collections",
            "2",
            "--top-k",
            "3",
            "--mode",
            "hybrid",
        ],
    ]
    for argv in commands:
        monkeypatch.setattr(sys, "argv", argv)
        cli.main()

    assert captured[0]["command"] == "list"
    assert captured[0]["registry_path"] == registry_path
    assert captured[1]["command"] == "route"
    assert captured[1]["collection"] == "recipes"
    assert captured[2]["command"] == "search"
    assert captured[2]["collection"] is None
    assert captured[2]["max_collections"] == 2
    assert captured[2]["top_k"] == 3
    assert captured[2]["mode"] == "hybrid"
