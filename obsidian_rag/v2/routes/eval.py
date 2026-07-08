from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v2.dependencies import get_retrieval_service
from obsidian_rag.v2.evaluation.answer import evaluate_answer_example
from obsidian_rag.v2.evaluation.dataset import load_eval_dataset
from obsidian_rag.v2.evaluation.retrieval import RetrievalEvaluator
from obsidian_rag.v2.schemas import AnswerEvalRequest, AnswerEvalResponse, RetrievalEvalRequest, RetrievalEvalResponse, resolve_output_path

router = APIRouter()


@router.post("/eval/retrieval", response_model=RetrievalEvalResponse)
def evaluate_retrieval(
    request: RetrievalEvalRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalEvalResponse:
    dataset = load_eval_dataset(Path(request.dataset_path).expanduser())
    evaluator = RetrievalEvaluator(retrieval_service)
    report = evaluator.evaluate_dataset(
        dataset,
        top_k=request.top_k,
        mode=request.mode,
        output_path=resolve_output_path(request),
    )
    return RetrievalEvalResponse.model_validate(report.to_dict())


@router.post("/eval/answer", response_model=AnswerEvalResponse)
def evaluate_answer(request: AnswerEvalRequest) -> AnswerEvalResponse:
    metrics = evaluate_answer_example(
        answer=request.answer,
        expected_source_files=request.expected_source_files,
        cited_source_files=request.cited_source_files,
        expected_answer_points=request.expected_answer_points,
    )
    return AnswerEvalResponse.model_validate(metrics.__dict__)
