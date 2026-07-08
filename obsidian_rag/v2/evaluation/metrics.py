from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalExampleMetrics:
    hit: bool
    first_relevant_rank: int | None
    reciprocal_rank: float
    source_recall: float
    matched_expected_source_files: list[str]
    missing_expected_source_files: list[str]


@dataclass(frozen=True)
class RetrievalSummaryMetrics:
    example_count: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float
    mean_source_recall: float


def evaluate_retrieval_example(
    expected_source_files: list[str],
    retrieved_source_files: list[str],
) -> RetrievalExampleMetrics:
    expected = _dedupe(expected_source_files)
    retrieved = _dedupe(retrieved_source_files)
    matched = [source for source in expected if source in retrieved]
    missing = [source for source in expected if source not in retrieved]

    first_rank = _first_relevant_rank(expected, retrieved_source_files)
    reciprocal_rank = 1 / first_rank if first_rank is not None else 0.0
    source_recall = len(matched) / len(expected) if expected else 0.0
    return RetrievalExampleMetrics(
        hit=bool(matched),
        first_relevant_rank=first_rank,
        reciprocal_rank=reciprocal_rank,
        source_recall=source_recall,
        matched_expected_source_files=matched,
        missing_expected_source_files=missing,
    )


def summarize_retrieval_metrics(examples: list[RetrievalExampleMetrics]) -> RetrievalSummaryMetrics:
    if not examples:
        return RetrievalSummaryMetrics(
            example_count=0,
            hit_rate_at_k=0.0,
            mean_reciprocal_rank=0.0,
            mean_source_recall=0.0,
        )
    count = len(examples)
    return RetrievalSummaryMetrics(
        example_count=count,
        hit_rate_at_k=sum(1 for example in examples if example.hit) / count,
        mean_reciprocal_rank=sum(example.reciprocal_rank for example in examples) / count,
        mean_source_recall=sum(example.source_recall for example in examples) / count,
    )


def _first_relevant_rank(expected: list[str], retrieved_source_files: list[str]) -> int | None:
    expected_set = set(expected)
    for rank, source in enumerate(retrieved_source_files, start=1):
        if source in expected_set:
            return rank
    return None


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
