from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import (
    ProductionAskRequest,
    ProductionAskResponse,
    RunError,
    RunEvent,
    RunMetrics,
    RunRecord,
    RunStatus,
    RunTiming,
    TokenEstimate,
    ToolRunSummary,
)


class AgentRuntimeService:
    """在 V3.8.1 Agent 外管理 Run 生命周期和可观察运行摘要。"""

    def __init__(self, agent_service, run_store: InMemoryRunStore):
        self.agent_service = agent_service
        self.run_store = run_store

    def ask(self, request: ProductionAskRequest) -> ProductionAskResponse:
        run_id = f"prod_{uuid4().hex[:12]}"
        started_at = _now()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            timing=RunTiming(started_at=started_at),
            events=[_event("run_queued", "queued", "请求已进入 V3.10 Production Run 生命周期。")],
        )
        self.run_store.save(record)

        record = record.model_copy(
            update={
                "status": "running",
                "events": [*record.events, _event("run_started", "running", "开始调用 V3.8.1 Agent。")],
            }
        )
        self.run_store.save(record)
        started = perf_counter()

        try:
            agent_response = self.agent_service.ask(request)
        except Exception as exc:
            finished_at = _now()
            record = record.model_copy(
                update={
                    "status": "failed",
                    "timing": RunTiming(
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=_elapsed_ms(started),
                    ),
                    "error": RunError(
                        error_type=type(exc).__name__,
                        message=_safe_error_message(exc),
                        retryable=False,
                    ),
                    "events": [*record.events, _event("run_failed", "failed", "Agent 调用异常结束。")],
                }
            )
            self.run_store.save(record)
            return ProductionAskResponse(run=record, agent_response=None)

        finished_at = _now()
        timing = RunTiming(
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=_elapsed_ms(started),
        )
        record = record.model_copy(
            update={
                "status": "succeeded",
                "agent_run_id": agent_response.run_id,
                "conversation_id": agent_response.conversation_id,
                "timing": timing,
                "metrics": _build_metrics(agent_response, timing),
                "events": [*record.events, _event("run_succeeded", "succeeded", "V3.8.1 Agent 已返回完整响应。")],
            }
        )
        self.run_store.save(record)
        return ProductionAskResponse(run=record, agent_response=agent_response)


def _build_metrics(response, timing: RunTiming) -> RunMetrics:
    step_results = [*response.step_results, *response.retry_step_results]
    answer_prompt = "\n".join(message.get("content", "") for message in response.context_bundle.messages)
    prompt_tokens = _estimate_tokens(answer_prompt)
    output_tokens = _estimate_tokens(response.answer)
    return RunMetrics(
        timing=timing,
        token_estimate=TokenEstimate(
            answer_prompt_tokens=prompt_tokens,
            answer_output_tokens=output_tokens,
            observed_total_tokens=prompt_tokens + output_tokens,
            method="中文字符约 2 字符/token、其他字符约 4 字符/token；仅统计可观察的 Answer prompt 与最终 answer，不是供应商计费 token。",
        ),
        graph_node_count=len(response.graph_path),
        trace_event_count=len(response.trace),
        retrieval_result_count=sum(result.result_count for result in step_results),
        tool_summaries=_tool_summaries(step_results),
    )


def _tool_summaries(step_results) -> list[ToolRunSummary]:
    grouped: dict[str, dict[str, int]] = {}
    for result in step_results:
        if not result.tool_name:
            continue
        summary = grouped.setdefault(
            result.tool_name,
            {"call_count": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0, "result_count": 0},
        )
        summary["call_count"] += 1
        summary[f"{result.status}_count"] += 1
        summary["result_count"] += result.result_count
    return [ToolRunSummary(tool_name=name, **summary) for name, summary in grouped.items()]


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk_count = sum(1 for character in text if "\u4e00" <= character <= "\u9fff")
    other_count = len(text) - cjk_count
    return max(1, cjk_count // 2 + other_count // 4)


def _event(name: str, status: RunStatus, detail: str) -> RunEvent:
    return RunEvent(name=name, status=status, occurred_at=_now(), detail=detail)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip() or "未提供异常消息。"
    return message[:500]
