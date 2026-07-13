from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from obsidian_rag.v3_9.schemas import (
    AgentEvalCase,
    AgentEvalCheck,
    AgentEvalDataset,
    AgentEvalDatasetReport,
    AgentEvalReport,
    AgentEvalSummary,
)


class AgentEvaluator:
    """运行 V3.8.1 Agent，并按 case contract 评测其可观察行为。"""

    def __init__(self, agent_service):
        self.agent_service = agent_service

    def evaluate_case(self, case: AgentEvalCase) -> AgentEvalReport:
        response = self.agent_service.ask(case.request)
        checks = _build_checks(case, response)
        passed_count = sum(check.passed for check in checks)
        score = passed_count / len(checks) if checks else 1.0
        return AgentEvalReport(
            case_id=case.id,
            passed=all(check.passed for check in checks),
            score=score,
            checks=checks,
            agent_response=response,
        )

    def evaluate_dataset(
        self,
        dataset: AgentEvalDataset,
        output_path: Path | None = None,
    ) -> AgentEvalDatasetReport:
        case_reports = [self.evaluate_case(case) for case in dataset.cases]
        case_count = len(case_reports)
        summary = AgentEvalSummary(
            case_count=case_count,
            passed_count=sum(report.passed for report in case_reports),
            pass_rate=sum(report.passed for report in case_reports) / case_count,
            mean_score=sum(report.score for report in case_reports) / case_count,
        )
        report = AgentEvalDatasetReport(
            summary=summary,
            cases=case_reports,
            output_path=str(output_path) if output_path else None,
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return report


def default_agent_eval_output_path(base_dir: Path = Path(".rag/eval")) -> Path:
    """生成带时间戳的 V3.9 批量评测报告路径。"""

    return base_dir / f"agent-v3-9-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"


def _build_checks(case: AgentEvalCase, response) -> list[AgentEvalCheck]:
    expect = case.expect
    checks: list[AgentEvalCheck] = []
    if expect.should_retrieve is not None:
        checks.append(
            _check(
                "routing",
                expect.should_retrieve,
                response.used_retrieval,
                "used_retrieval 与预期一致。",
                "used_retrieval 与预期不一致。",
            )
        )
    if expect.required_step_kinds is not None:
        actual_kinds = [step.kind for step in response.plan.steps]
        checks.append(
            _check_subset(
                "plan",
                expect.required_step_kinds,
                actual_kinds,
                "Plan 包含所有必需的 step.kind。",
                "Plan 缺少必需的 step.kind。",
            )
        )
    if expect.expected_tools is not None:
        actual_tools = _tool_names(response)
        checks.append(
            _check_exact_or_subset(
                "tools",
                expect.expected_tools,
                actual_tools,
                "工具调用符合预期。",
                "工具调用与预期不一致。",
            )
        )
    if expect.expected_chunk_ids is not None:
        actual_chunk_ids = _chunk_ids(response)
        checks.append(
            _check_subset(
                "retrieval_chunks",
                expect.expected_chunk_ids,
                actual_chunk_ids,
                "检索结果命中所有预期 chunk_id。",
                "检索结果缺少预期 chunk_id。",
            )
        )
    if expect.expected_source_files is not None:
        actual_sources = _source_files(response)
        checks.append(
            _check_subset(
                "retrieval_sources",
                expect.expected_source_files,
                actual_sources,
                "检索结果命中所有预期来源文件。",
                "检索结果缺少预期来源文件。",
            )
        )
    if expect.evidence_sufficient is not None:
        checks.append(
            _check(
                "evidence",
                expect.evidence_sufficient,
                response.evidence_check.is_sufficient,
                "Evidence Checker 判定符合预期。",
                "Evidence Checker 判定与预期不一致。",
            )
        )
    if expect.expected_answer_points is not None:
        matched = [point for point in expect.expected_answer_points if point in response.answer]
        checks.append(
            AgentEvalCheck(
                name="answer",
                passed=len(matched) == len(expect.expected_answer_points),
                expected=expect.expected_answer_points,
                actual=matched,
                detail="答案覆盖所有关键点。" if len(matched) == len(expect.expected_answer_points) else "答案缺少部分关键点。",
            )
        )
    return checks


def _tool_names(response) -> list[str]:
    return _dedupe(
        [
            result.tool_name
            for result in [*response.step_results, *response.retry_step_results]
            if result.tool_name
        ]
    )


def _chunk_ids(response) -> list[str]:
    return _dedupe(
        [
            result.chunk_id
            for step_result in [*response.step_results, *response.retry_step_results]
            for result in step_result.results
            if result.chunk_id
        ]
    )


def _source_files(response) -> list[str]:
    return _dedupe(
        [
            result.source
            for step_result in [*response.step_results, *response.retry_step_results]
            for result in step_result.results
        ]
    )


def _check(name: str, expected, actual, passed_detail: str, failed_detail: str) -> AgentEvalCheck:
    return AgentEvalCheck(
        name=name,
        passed=actual == expected,
        expected=expected,
        actual=actual,
        detail=passed_detail if actual == expected else failed_detail,
    )


def _check_subset(name: str, expected: list[str], actual: list[str], passed_detail: str, failed_detail: str) -> AgentEvalCheck:
    passed = set(expected).issubset(actual)
    return AgentEvalCheck(
        name=name,
        passed=passed,
        expected=expected,
        actual=actual,
        detail=passed_detail if passed else failed_detail,
    )


def _check_exact_or_subset(
    name: str,
    expected: list[str],
    actual: list[str],
    passed_detail: str,
    failed_detail: str,
) -> AgentEvalCheck:
    passed = actual == [] if expected == [] else set(expected).issubset(actual)
    return AgentEvalCheck(
        name=name,
        passed=passed,
        expected=expected,
        actual=actual,
        detail=passed_detail if passed else failed_detail,
    )


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
