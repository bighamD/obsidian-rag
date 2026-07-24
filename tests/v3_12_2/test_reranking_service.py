from __future__ import annotations

from time import sleep

from obsidian_rag.reranking.providers import FakeReranker
from obsidian_rag.reranking.service import RerankingService
from obsidian_rag.schema import SearchResult, TextChunk


def _result(text: str, score: float, *, parent_id: str | None = None) -> SearchResult:
    metadata = {"source": f"{text}.md", "matched_child_text": text, "returned_parent_text": f"parent:{text}"}
    if parent_id:
        metadata["parent_id"] = parent_id
    return SearchResult(TextChunk(f"parent:{text}", metadata), score)


def test_fake_reranker_corrects_retrieval_order_and_preserves_scores():
    service = RerankingService(
        FakeReranker(lambda _query, document: 10.0 if "safe" in document else 1.0),
        enabled=True,
        provider="fake",
        model="deterministic-fake",
        device="cpu",
        timeout_seconds=1,
    )

    outcome = service.rerank("food", [_result("noise", 0.9), _result("safe", 0.5)], top_k=2)

    assert [item.result.chunk.metadata["source"] for item in outcome.items] == ["safe.md", "noise.md"]
    assert outcome.items[0].retrieval_rank == 2
    assert outcome.items[0].retrieval_score == 0.5
    assert outcome.items[0].rerank_score == 10.0
    assert outcome.summary.fallback is False


def test_disabled_and_empty_candidates_do_not_call_provider():
    class ExplodingProvider:
        provider = "fake"
        model = "exploding"
        device = "cpu"

        def score(self, query, documents):
            raise AssertionError("provider should not be called")

    service = RerankingService(
        ExplodingProvider(),
        enabled=False,
        provider="fake",
        model="exploding",
        device="cpu",
        timeout_seconds=1,
    )
    baseline = service.rerank("q", [_result("a", 0.8)], top_k=1)
    empty = service.rerank("q", [], top_k=1)

    assert baseline.items[0].rerank_score is None
    assert empty.items == []


def test_provider_error_and_timeout_fail_open():
    class BrokenProvider:
        provider = "fake"
        model = "broken"
        device = "cpu"

        def score(self, query, documents):
            raise RuntimeError("secret provider failure")

    class SlowProvider(BrokenProvider):
        model = "slow"

        def score(self, query, documents):
            sleep(0.05)
            return [1.0] * len(documents)

    broken = RerankingService(BrokenProvider(), enabled=True, provider="fake", model="broken", device="cpu", timeout_seconds=1)
    slow = RerankingService(SlowProvider(), enabled=True, provider="fake", model="slow", device="cpu", timeout_seconds=0.001)

    assert broken.rerank("q", [_result("a", 0.8)], top_k=1).summary.fallback is True
    timeout = slow.rerank("q", [_result("a", 0.8)], top_k=1)
    assert timeout.summary.fallback_reason == "reranker_timeout"
