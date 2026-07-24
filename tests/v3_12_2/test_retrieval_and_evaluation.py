from __future__ import annotations

from dataclasses import replace

from obsidian_rag.config import RagConfig
from obsidian_rag.reranking.providers import FakeReranker
from obsidian_rag.reranking.retrieval import RerankingRetrievalService
from obsidian_rag.reranking.service import RerankingService
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_12_2.evaluation import ranking_metrics


class BaseRetrieval:
    def __init__(self, by_collection=None):
        self.by_collection = by_collection or {}
        self.calls = []

    def search(self, query, top_k, mode, filters=None, collection=None):
        self.calls.append((query, top_k, collection))
        return list(self.by_collection.get(collection, self.by_collection.get(None, [])))[:top_k]

    def collection_name(self, collection=None):
        return collection or "default"


def _config() -> RagConfig:
    return RagConfig(
        api_key="",
        base_url="http://example.test/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=3,
        embedding_provider="hash",
        ollama_base_url="http://localhost",
        qdrant_url=None,
        db_path=__import__("pathlib").Path(".rag/test"),
        collection_name="default",
        min_score=0.0,
        vault_path=None,
        rerank_enabled=True,
        rerank_provider="fake",
        rerank_candidates=4,
        rerank_top_k=2,
    )


def _result(name: str, score: float, parent: str) -> SearchResult:
    return SearchResult(
        TextChunk(
            f"parent {name}",
            {
                "source": f"{name}.md",
                "parent_id": parent,
                "matched_child_text": name,
                "returned_parent_text": f"parent {name}",
            },
        ),
        score,
    )


def test_retrieval_expands_candidate_count_then_returns_rerank_top_k():
    base = BaseRetrieval({None: [_result("first", 0.9, "p1"), _result("winner", 0.4, "p2")]})
    reranker = RerankingService(
        FakeReranker(lambda _q, text: 5 if "winner" in text else 1),
        enabled=True,
        provider="fake",
        model="fake",
        device="cpu",
        timeout_seconds=1,
    )
    service = RerankingRetrievalService(base, reranker, _config())

    outcome = service.search_with_outcome("q", top_k=2)

    assert base.calls[0][1] == 4
    assert outcome.results[0].chunk.metadata["parent_id"] == "p2"
    assert outcome.results[0].chunk.text == "parent winner"
    assert outcome.results[0].chunk.metadata["rerank_run"]["provider"] == "fake"


def test_multi_collection_candidates_are_unified_before_reranking():
    base = BaseRetrieval(
        {
            "food": [_result("food", 0.8, "food-parent")],
            "recipes": [_result("recipe winner", 0.7, "recipe-parent")],
        }
    )
    reranker = RerankingService(
        FakeReranker(lambda _q, text: 9 if "winner" in text else 1),
        enabled=True,
        provider="fake",
        model="fake",
        device="cpu",
        timeout_seconds=1,
    )
    service = RerankingRetrievalService(base, reranker, _config())

    outcome, errors = service.search_collections("q", ["food", "recipes"], top_k=2)

    assert errors == {}
    assert outcome.results[0].chunk.metadata["collection"] == "recipes"


def test_ranking_metrics_reports_mrr_and_ndcg_improvement_shape():
    baseline = ranking_metrics(["wrong", "relevant"], {"relevant"}, 2)
    reranked = ranking_metrics(["relevant", "wrong"], {"relevant"}, 2)

    assert baseline["mrr"] == 0.5
    assert reranked["mrr"] == 1.0
    assert reranked["ndcg_at_k"] > baseline["ndcg_at_k"]
