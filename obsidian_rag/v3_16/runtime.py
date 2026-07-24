from __future__ import annotations

from threading import Thread
from time import perf_counter
from uuid import uuid4

from obsidian_rag.v3_10.runtime.lifecycle import _build_metrics, _elapsed_ms, _event, _now, _safe_error_message
from obsidian_rag.v3_10.schemas import RunError, RunRecord, RunTiming
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput
from obsidian_rag.v3_16.schemas import (
    DeepAgentAskRequest,
    DeepAgentAskResponse,
    DeepAgentExecutionResult,
)
from obsidian_rag.v3_16.store import PostgresDeepAgentStore


class DeepAgentRuntimeService:
    """管理 DeepAgents 单次 Run、SSE、持久审批与兼容响应。"""

    def __init__(self, agent_factory, store: PostgresDeepAgentStore, event_bus: RunEventBus):
        self.agent_factory = agent_factory
        self.store = store
        self.event_bus = event_bus

    def ask(self, request: DeepAgentAskRequest) -> DeepAgentAskResponse:
        run_id, request, record = self._prepare_run(request)
        record = self._running(record, "开始执行 V3.16 DeepAgents Tool Loop。")
        started = perf_counter()
        try:
            result = self.agent_factory().begin(request, run_id)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def resume(self, run_id: str, decision: ApprovalDecisionInput) -> DeepAgentAskResponse:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "waiting_for_approval":
            raise ValueError(f"Run is not waiting for approval: {run_id}")
        record = self._running(record, f"收到人工决定 {decision.action}，恢复 DeepAgents Graph。")
        started = perf_counter()
        try:
            result = self.agent_factory().resume(run_id, decision)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def start_stream(self, request: DeepAgentAskRequest) -> str:
        run_id, request, record = self._prepare_run(request)
        self.event_bus.create_run(run_id)
        self._publish(record, "run_queued", "queued", "请求已进入 V3.16 DeepAgents 生命周期。")
        Thread(target=self._run_stream, args=(run_id, request, None), daemon=True).start()
        return run_id

    def start_resume_stream(self, run_id: str, decision: ApprovalDecisionInput) -> str:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "waiting_for_approval":
            raise ValueError(f"Run is not waiting for approval: {run_id}")
        self.event_bus.create_run(run_id)
        Thread(target=self._run_stream, args=(run_id, None, decision), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        return self.event_bus.iter_sse(run_id)

    def get_response(self, run_id: str) -> DeepAgentAskResponse | None:
        return self.store.get_response(run_id)

    def _prepare_run(self, request: DeepAgentAskRequest) -> tuple[str, DeepAgentAskRequest, RunRecord]:
        run_id = f"deep_{uuid4().hex[:12]}"
        normalized = request.model_copy(
            update={"conversation_id": request.conversation_id or f"conv_{uuid4().hex[:12]}"}
        )
        record = self._new_record(run_id)
        self.store.save_request(run_id, normalized)
        return run_id, normalized, record

    def _run_stream(
        self,
        run_id: str,
        request: DeepAgentAskRequest | None,
        decision: ApprovalDecisionInput | None,
    ) -> None:
        record = self.store.get(run_id)
        if record is None:
            return
        detail = (
            "开始执行 V3.16 DeepAgents Tool Loop。"
            if request is not None
            else f"收到人工决定 {decision.action}，恢复 DeepAgents Graph。"
        )
        record = self._running(record, detail)
        self._publish(record, "run_started" if request is not None else "run_resumed", "running", detail)
        started = perf_counter()

        def event_sink(name: str, payload: dict) -> None:
            current = self.store.get(run_id) or record
            data = payload if name in {"answer_delta", "reasoning_delta"} else {"agent": payload}
            self._publish(current, name, "running", _agent_event_detail(name, payload), data)

        try:
            agent = self.agent_factory()
            result = (
                agent.begin(request, run_id, event_sink)
                if request is not None
                else agent.resume(run_id, decision, event_sink)
            )
        except Exception as exc:
            response = self._failed(record, exc, started)
            self._publish(
                response.run,
                "run_failed",
                "failed",
                "Deep Agent 调用异常结束。",
                {"response": response.model_dump(mode="json")},
            )
            return
        response = self._complete(record, result, started)
        event_name = "run_waiting_for_approval" if result.status == "waiting_for_approval" else "run_succeeded"
        detail = (
            "DeepAgents Graph 已在 write_file 前持久化并暂停。"
            if result.status == "waiting_for_approval"
            else "DeepAgents Tool Loop 已执行完成。"
        )
        self._publish(
            response.run,
            event_name,
            response.run.status,
            detail,
            {"response": response.model_dump(mode="json")},
        )

    def _new_record(self, run_id: str) -> RunRecord:
        record = RunRecord(
            run_id=run_id,
            status="queued",
            timing=RunTiming(started_at=_now()),
            events=[_event("run_queued", "queued", "请求已进入 V3.16 DeepAgents 生命周期。")],
        )
        return self.store.save(record)

    def _running(self, record: RunRecord, detail: str) -> RunRecord:
        updated = record.model_copy(
            update={
                "status": "running",
                "events": [*record.events, _event("run_started", "running", detail)],
                "error": None,
            }
        )
        return self.store.save(updated)

    def _complete(self, record: RunRecord, result: DeepAgentExecutionResult, started: float) -> DeepAgentAskResponse:
        duration_ms = (record.timing.duration_ms or 0) + _elapsed_ms(started)
        if result.status == "waiting_for_approval":
            updated = record.model_copy(
                update={
                    "status": "waiting_for_approval",
                    "agent_run_id": result.native_response.run_id,
                    "conversation_id": result.compatibility_response.conversation_id,
                    "timing": record.timing.model_copy(update={"duration_ms": duration_ms}),
                    "events": [
                        *record.events,
                        _event(
                            "run_waiting_for_approval",
                            "waiting_for_approval",
                            "DeepAgents Graph 已在写入前暂停。",
                        ),
                    ],
                }
            )
        else:
            timing = RunTiming(
                started_at=record.timing.started_at,
                finished_at=_now(),
                duration_ms=duration_ms,
            )
            updated = record.model_copy(
                update={
                    "status": "succeeded",
                    "agent_run_id": result.native_response.run_id,
                    "conversation_id": result.compatibility_response.conversation_id,
                    "timing": timing,
                    "metrics": _build_metrics(result.compatibility_response, timing),
                    "events": [
                        *record.events,
                        _event("run_succeeded", "succeeded", "DeepAgents Tool Loop 已执行完成。"),
                    ],
                }
            )
        self.store.save(updated)
        response = DeepAgentAskResponse(
            run=updated,
            agent_response=result.compatibility_response,
            deep_agent_response=result.native_response,
            approval=result.approval,
        )
        self.store.save_artifacts(updated.run_id, result.native_response.artifacts)
        self.store.save_response(response)
        return response

    def _failed(self, record: RunRecord, exc: Exception, started: float) -> DeepAgentAskResponse:
        timing = RunTiming(
            started_at=record.timing.started_at,
            finished_at=_now(),
            duration_ms=(record.timing.duration_ms or 0) + _elapsed_ms(started),
        )
        updated = record.model_copy(
            update={
                "status": "failed",
                "timing": timing,
                "error": RunError(
                    error_type=type(exc).__name__,
                    message=_safe_error_message(exc),
                    retryable=False,
                ),
                "events": [*record.events, _event("run_failed", "failed", "Deep Agent 调用异常结束。")],
            }
        )
        self.store.save(updated)
        previous = self.store.get_response(record.run_id)
        response = DeepAgentAskResponse(
            run=updated,
            agent_response=previous.agent_response if previous else None,
            deep_agent_response=previous.deep_agent_response if previous else None,
            approval=self.store.get_approval(record.run_id),
        )
        if self.store.get_request(record.run_id) is not None:
            self.store.save_response(response)
        return response

    def _publish(self, record: RunRecord, name: str, status, detail: str, data: dict | None = None) -> None:
        self.event_bus.publish(
            record.run_id,
            name,
            status,
            detail,
            {"run": record.model_dump(mode="json"), **(data or {})},
        )


def _agent_event_detail(name: str, payload: dict) -> str:
    if name == "progress":
        return f"Deep Agent 阶段 {payload.get('phase', 'unknown')}：{payload.get('status', 'running')}。"
    if name == "node_finished":
        return f"DeepAgents 节点 {payload.get('node_name', 'unknown')} 已完成。"
    if name == "tool_started":
        return f"开始调用工具 {payload.get('tool_name', 'unknown')}。"
    if name == "tool_finished":
        return f"工具 {payload.get('tool_name', 'unknown')} 调用{payload.get('status', 'completed')}。"
    if name == "answer_delta":
        return "Deep Agent 产生最终可见答案。"
    return f"Deep Agent 产生 {name} 事件。"

