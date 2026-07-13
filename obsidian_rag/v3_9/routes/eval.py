from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from obsidian_rag.v3_9.dependencies import get_agent_evaluator
from obsidian_rag.v3_9.evaluation.dataset import load_agent_eval_dataset
from obsidian_rag.v3_9.evaluation.evaluator import AgentEvaluator, default_agent_eval_output_path
from obsidian_rag.v3_9.schemas import AgentEvalCase, AgentEvalDatasetReport, AgentEvalDatasetRequest, AgentEvalReport


router = APIRouter()


@router.post("/eval/agent", response_model=AgentEvalReport)
def evaluate_agent_case(
    case: AgentEvalCase,
    evaluator: AgentEvaluator = Depends(get_agent_evaluator),
) -> AgentEvalReport:
    return evaluator.evaluate_case(case)


@router.post("/eval/agent/dataset", response_model=AgentEvalDatasetReport)
def evaluate_agent_dataset(
    request: AgentEvalDatasetRequest,
    evaluator: AgentEvaluator = Depends(get_agent_evaluator),
) -> AgentEvalDatasetReport:
    output_path = None
    if request.save:
        output_path = Path(request.output_path).expanduser() if request.output_path else default_agent_eval_output_path()
    dataset = load_agent_eval_dataset(Path(request.dataset_path))
    return evaluator.evaluate_dataset(dataset, output_path=output_path)
