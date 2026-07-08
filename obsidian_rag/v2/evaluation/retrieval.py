from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import SearchMode
from obsidian_rag.v2.evaluation.dataset import EvalDataset, EvalExample
from obsidian_rag.v2.evaluation.metrics import (
    RetrievalExampleMetrics,
    RetrievalSummaryMetrics,
    evaluate_retrieval_example,
    summarize_retrieval_metrics,
)


@dataclass(frozen=True)
class RetrievalEvalExampleResult:
    id: str
    question: str
    expected_source_files: list[str]
    retrieved_source_files: list[str]
    hit: bool
    first_relevant_rank: int | None
    reciprocal_rank: float
    source_recall: float
    matched_expected_source_files: list[str]
    missing_expected_source_files: list[str]


@dataclass(frozen=True)
class RetrievalEvalReport:
    mode: str
    top_k: int
    summary: RetrievalSummaryMetrics
    examples: list[RetrievalEvalExampleResult]
    output_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetrievalEvaluator:
    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    def evaluate_dataset(
        self,
        dataset: EvalDataset,
        top_k: int = 5,
        mode: SearchMode = "hybrid",
        output_path: Path | None = None,
    ) -> RetrievalEvalReport:
        example_results = [
            self._evaluate_example(example, top_k=top_k, mode=mode)
            for example in dataset.examples
        ]
        summary = summarize_retrieval_metrics(
            [
                RetrievalExampleMetrics(
                    hit=result.hit,
                    first_relevant_rank=result.first_relevant_rank,
                    reciprocal_rank=result.reciprocal_rank,
                    source_recall=result.source_recall,
                    matched_expected_source_files=result.matched_expected_source_files,
                    missing_expected_source_files=result.missing_expected_source_files,
                )
                for result in example_results
            ]
        )
        report = RetrievalEvalReport(
            mode=mode,
            top_k=top_k,
            summary=summary,
            examples=example_results,
            output_path=str(output_path) if output_path else None,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return report

    def _evaluate_example(
        self,
        example: EvalExample,
        top_k: int,
        mode: SearchMode,
    ) -> RetrievalEvalExampleResult:
        results = self.retrieval_service.search(example.question, top_k=top_k, mode=mode)
        retrieved_source_files = [_source_file(result) for result in results]
        metrics = evaluate_retrieval_example(example.expected_source_files, retrieved_source_files)
        return RetrievalEvalExampleResult(
            id=example.id,
            question=example.question,
            expected_source_files=example.expected_source_files,
            retrieved_source_files=retrieved_source_files,
            hit=metrics.hit,
            first_relevant_rank=metrics.first_relevant_rank,
            reciprocal_rank=metrics.reciprocal_rank,
            source_recall=metrics.source_recall,
            matched_expected_source_files=metrics.matched_expected_source_files,
            missing_expected_source_files=metrics.missing_expected_source_files,
        )


def default_retrieval_eval_output_path(base_dir: Path = Path(".rag/eval")) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return base_dir / f"retrieval-{timestamp}.json"


def _source_file(result: SearchResult | RankedSearchResult) -> str:
    return str(result.chunk.metadata.get("source", "unknown"))
