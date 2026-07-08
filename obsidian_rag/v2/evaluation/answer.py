from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerExampleMetrics:
    source_coverage: float
    answer_point_coverage: float
    citation_present: bool
    matched_source_files: list[str]
    missing_source_files: list[str]
    matched_answer_points: list[str]
    missing_answer_points: list[str]


def evaluate_answer_example(
    answer: str,
    expected_source_files: list[str],
    cited_source_files: list[str],
    expected_answer_points: list[str],
) -> AnswerExampleMetrics:
    expected_sources = _dedupe(expected_source_files)
    cited_sources = set(_dedupe(cited_source_files))
    matched_sources = [source for source in expected_sources if source in cited_sources]
    missing_sources = [source for source in expected_sources if source not in cited_sources]

    expected_points = _dedupe(expected_answer_points)
    matched_points = [point for point in expected_points if point in answer]
    missing_points = [point for point in expected_points if point not in answer]

    return AnswerExampleMetrics(
        source_coverage=len(matched_sources) / len(expected_sources) if expected_sources else 0.0,
        answer_point_coverage=len(matched_points) / len(expected_points) if expected_points else 0.0,
        citation_present=bool(cited_source_files),
        matched_source_files=matched_sources,
        missing_source_files=missing_sources,
        matched_answer_points=matched_points,
        missing_answer_points=missing_points,
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
