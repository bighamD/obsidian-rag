from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import replace
from time import perf_counter

from obsidian_rag.config import RagConfig
from obsidian_rag.reranking.models import RerankItem, RerankOutcome, RerankRunSummary, SearchLikeResult
from obsidian_rag.reranking.providers import CrossEncoderReranker, FakeReranker, Reranker
from obsidian_rag.schema import TextChunk


class RerankingService:
    """执行重排并在任何 Provider 故障时 fail-open 回退原始顺序。"""

    def __init__(
        self,
        reranker: Reranker | None,
        *,
        enabled: bool,
        provider: str,
        model: str | None,
        device: str | None,
        timeout_seconds: float,
    ):
        self.reranker = reranker
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.device = device
        self.timeout_seconds = timeout_seconds

    def rerank(self, query: str, results: list[SearchLikeResult], *, top_k: int) -> RerankOutcome:
        started = perf_counter()
        candidates = list(results)
        if not candidates:
            return self._baseline([], top_k, started)
        if not self.enabled or self.provider == "none" or self.reranker is None:
            return self._baseline(candidates, top_k, started)

        scoring_texts = [_scoring_text(result) for result in candidates]
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-reranker")
        future = executor.submit(self.reranker.score, query, scoring_texts)
        try:
            scores = future.result(timeout=self.timeout_seconds)
            if len(scores) != len(candidates):
                raise ValueError("Reranker returned a score count different from candidate count")
        except FutureTimeoutError:
            future.cancel()
            return self._fallback(candidates, top_k, started, "reranker_timeout")
        except Exception as exc:
            return self._fallback(candidates, top_k, started, f"{type(exc).__name__}: {_safe_error(exc)}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        ranked = sorted(enumerate(scores), key=lambda item: (-float(item[1]), item[0]))
        items = []
        for rerank_rank, (index, score) in enumerate(ranked[:top_k], start=1):
            result = _with_rerank_metadata(
                candidates[index],
                retrieval_rank=index + 1,
                rerank_rank=rerank_rank,
                rerank_score=float(score),
            )
            items.append(
                RerankItem(
                    result=result,
                    retrieval_rank=index + 1,
                    retrieval_score=float(candidates[index].score),
                    rerank_rank=rerank_rank,
                    rerank_score=float(score),
                    scoring_text=scoring_texts[index],
                )
            )
        return RerankOutcome(
            items=items,
            summary=self._summary(len(candidates), len(items), started),
        )

    def _baseline(self, results: list[SearchLikeResult], top_k: int, started: float) -> RerankOutcome:
        items = [
            RerankItem(
                result=_with_rerank_metadata(result, rank, rank, None),
                retrieval_rank=rank,
                retrieval_score=float(result.score),
                rerank_rank=rank,
                rerank_score=None,
                scoring_text=_scoring_text(result),
            )
            for rank, result in enumerate(results[:top_k], start=1)
        ]
        return RerankOutcome(items=items, summary=self._summary(len(results), len(items), started))

    def _fallback(
        self,
        results: list[SearchLikeResult],
        top_k: int,
        started: float,
        reason: str,
    ) -> RerankOutcome:
        baseline = self._baseline(results, top_k, started)
        return replace(
            baseline,
            summary=replace(baseline.summary, fallback=True, fallback_reason=reason),
        )

    def _summary(self, candidate_count: int, output_count: int, started: float) -> RerankRunSummary:
        return RerankRunSummary(
            enabled=self.enabled,
            provider=self.provider,
            model=self.model,
            device=self.device,
            candidate_count=candidate_count,
            output_count=output_count,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )


def build_reranking_service(config: RagConfig, reranker: Reranker | None = None) -> RerankingService:
    if reranker is None and config.rerank_enabled:
        if config.rerank_provider == "sentence_transformers":
            reranker = CrossEncoderReranker(
                config.rerank_model,
                device=config.rerank_device,
                batch_size=config.rerank_batch_size,
            )
        elif config.rerank_provider == "fake":
            reranker = FakeReranker()
    return RerankingService(
        reranker,
        enabled=config.rerank_enabled,
        provider=config.rerank_provider,
        model=config.rerank_model if config.rerank_provider != "none" else None,
        device=config.rerank_device if config.rerank_provider != "none" else None,
        timeout_seconds=config.rerank_timeout_seconds,
    )


def _scoring_text(result: SearchLikeResult) -> str:
    metadata = result.chunk.metadata
    child = str(metadata.get("matched_child_text") or result.chunk.text)
    headings = " > ".join(str(item) for item in metadata.get("heading_path", []))
    return f"{headings}\n\n{child}" if headings else child


def _with_rerank_metadata(
    result: SearchLikeResult,
    retrieval_rank: int,
    rerank_rank: int,
    rerank_score: float | None,
) -> SearchLikeResult:
    metadata = {
        **result.chunk.metadata,
        "retrieval_rank": retrieval_rank,
        "retrieval_score": float(result.score),
        "rerank_rank": rerank_rank,
        "rerank_score": rerank_score,
    }
    return replace(result, chunk=TextChunk(text=result.chunk.text, metadata=metadata))


def _safe_error(exc: Exception) -> str:
    return (str(exc).strip() or type(exc).__name__)[:300]
