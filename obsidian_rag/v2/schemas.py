from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from obsidian_rag.v1.schemas import SearchMode


class RetrievalEvalRequest(BaseModel):
    dataset_path: str = Field(description="Path to a YAML eval dataset")
    top_k: int = Field(default=5, ge=1, le=50)
    mode: SearchMode = "hybrid"
    save: bool = True
    output_path: str | None = None


class RetrievalExampleResultResponse(BaseModel):
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


class RetrievalSummaryResponse(BaseModel):
    example_count: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float
    mean_source_recall: float


class RetrievalEvalResponse(BaseModel):
    mode: str
    top_k: int
    summary: RetrievalSummaryResponse
    examples: list[RetrievalExampleResultResponse]
    output_path: str | None = None


class AnswerEvalRequest(BaseModel):
    answer: str = Field(min_length=1)
    expected_source_files: list[str] = Field(default_factory=list)
    cited_source_files: list[str] = Field(default_factory=list)
    expected_answer_points: list[str] = Field(default_factory=list)


class AnswerEvalResponse(BaseModel):
    source_coverage: float
    answer_point_coverage: float
    citation_present: bool
    matched_source_files: list[str]
    missing_source_files: list[str]
    matched_answer_points: list[str]
    missing_answer_points: list[str]


def resolve_output_path(request: RetrievalEvalRequest) -> Path | None:
    if not request.save:
        return None
    if request.output_path:
        return Path(request.output_path).expanduser()
    from obsidian_rag.v2.evaluation.retrieval import default_retrieval_eval_output_path

    return default_retrieval_eval_output_path()
