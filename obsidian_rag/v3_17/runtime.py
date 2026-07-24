from __future__ import annotations

from threading import Thread
from time import perf_counter
from uuid import uuid4

from obsidian_rag.v3_10.runtime.lifecycle import _build_metrics, _elapsed_ms, _event, _now, _safe_error_message
from obsidian_rag.v3_10.schemas import RunError, RunRecord, RunTiming
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput
from obsidian_rag.v3_17.schemas import (
    DurableAgentAskRequest,
    DurableAgentAskResponse,
    DurableExecutionResult,
)
from obsidian_rag.v3_17.store import PostgresDurableAgentStore


class DurableAgentRuntimeService:
    """管理 V3.17 Run、稳定 Conversation Thread、SSE 与持久恢复。"""

    def __init__(self, agent_factory, store: PostgresDurableAgentStore, event_bus: RunEventBus):
        self.agent_factory = agent_factory
        self.store = store
        self.event_bus = event_bus

    def ask(self, request: DurableAgentAskRequest) -> DurableAgentAskResponse:
        run_id, request, record = self._prepare_run(request)
        record = self._running(record, "开始执行 V3.17 Durable Memory Tool Loop。")
        started = perf_counter()
        try:
            result = self.agent_factory().begin(request, run_id)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def resume(self, run_id: str, decision: ApprovalDecisionInput) -> DurableAgentAskResponse:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "waiting_for_approval":
            raise ValueError(f"Run is not waiting for approval: {run_id}")
        record = self._running(record, f"收到人工决定 {decision.action}，恢复 V3.17 DeepAgents Graph。")
        started = perf_counter()
        try:
            result = self.agent_factory().resume(run_id, decision)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def recover(self, run_id: str) -> DurableAgentAskResponse:
        """同步恢复 failed Run，并沿用原 Conversation 的稳定 Thread。"""

        record = self._recoverable_record(run_id)
        record = self._running(record, "从稳定 Thread 的最近 PostgreSQL Checkpoint 重试失败节点。")
        started = perf_counter()
        try:
            result = self.agent_factory().recover(run_id)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def start_stream(self, request: DurableAgentAskRequest) -> str:
        run_id, request, record = self._prepare_run(request)
        self.event_bus.create_run(run_id)
        self._publish(record, "run_queued", "queued", "请求已进入 V3.17 Durable Memory 生命周期。")
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

    def start_recovery_stream(self, run_id: str) -> str:
        """通过 SSE 从 failed Run 的最近 Checkpoint 继续执行。"""

        self._recoverable_record(run_id)
        self.event_bus.create_run(run_id)
        Thread(target=self._run_recovery_stream, args=(run_id,), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        return self.event_bus.iter_sse(run_id)

    def get_response(self, run_id: str) -> DurableAgentAskResponse | None:
        return self.store.get_response(run_id)

    def _prepare_run(self, request: DurableAgentAskRequest) -> tuple[str, DurableAgentAskRequest, RunRecord]:
        run_id = f"durable_{uuid4().hex[:12]}"
        conversation = self.store.get_or_create_conversation(request)
        normalized = request.model_copy(update={"conversation_id": conversation.conversation_id})
        record = self._new_record(run_id, conversation.conversation_id)
        self.store.save_request(run_id, normalized, conversation)
        return run_id, normalized, record

    def _run_stream(
        self,
        run_id: str,
        request: DurableAgentAskRequest | None,
        decision: ApprovalDecisionInput | None,
    ) -> None:
        record = self.store.get(run_id)
        if record is None:
            return
        detail = (
            "开始执行 V3.17 Durable Memory Tool Loop。"
            if request is not None
            else f"收到人工决定 {decision.action}，恢复 V3.17 DeepAgents Graph。"
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
                "V3.17 Durable Agent 调用异常结束。",
                {"response": response.model_dump(mode="json")},
            )
            return
        response = self._complete(record, result, started)
        event_name = "run_waiting_for_approval" if result.status == "waiting_for_approval" else "run_succeeded"
        detail = (
            "DeepAgents Graph 已在 Artifact 写入前持久化并暂停。"
            if result.status == "waiting_for_approval"
            else "V3.17 Durable Memory Tool Loop 已执行完成。"
        )
        self._publish(
            response.run,
            event_name,
            response.run.status,
            detail,
            {"response": response.model_dump(mode="json")},
        )

    def _run_recovery_stream(self, run_id: str) -> None:
        record = self.store.get(run_id)
        if record is None:
            return
        detail = "从稳定 Thread 的最近 PostgreSQL Checkpoint 重试失败节点。"
        record = self._running(record, detail)
        self._publish(record, "run_recovering", "running", detail)
        started = perf_counter()

        def event_sink(name: str, payload: dict) -> None:
            current = self.store.get(run_id) or record
            data = payload if name in {"answer_delta", "reasoning_delta"} else {"agent": payload}
            self._publish(current, name, "running", _agent_event_detail(name, payload), data)

        try:
            result = self.agent_factory().recover(run_id, event_sink)
        except Exception as exc:
            response = self._failed(record, exc, started)
            self._publish(
                response.run,
                "run_failed",
                "failed",
                "V3.17 Checkpoint 恢复仍然失败。",
                {"response": response.model_dump(mode="json")},
            )
            return
        response = self._complete(record, result, started)
        event_name = "run_waiting_for_approval" if result.status == "waiting_for_approval" else "run_succeeded"
        detail = (
            "恢复后 Graph 在 Artifact 写入前再次暂停。"
            if result.status == "waiting_for_approval"
            else "失败节点已从稳定 Thread Checkpoint 恢复并执行完成。"
        )
        self._publish(
            response.run,
            event_name,
            response.run.status,
            detail,
            {"response": response.model_dump(mode="json")},
        )

    def _new_record(self, run_id: str, conversation_id: str) -> RunRecord:
        record = RunRecord(
            run_id=run_id,
            conversation_id=conversation_id,
            status="queued",
            timing=RunTiming(started_at=_now()),
            events=[_event("run_queued", "queued", "请求已进入 V3.17 Durable Memory 生命周期。")],
        )
        return self.store.save(record)

    def _recoverable_record(self, run_id: str) -> RunRecord:
        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status == "waiting_for_approval":
            raise ValueError(f"Run is waiting for approval, use resume instead: {run_id}")
        if record.status != "failed":
            raise ValueError(f"Run is not failed: {run_id}")
        return record

    def _running(self, record: RunRecord, detail: str) -> RunRecord:
        updated = record.model_copy(
            update={
                "status": "running",
                "events": [*record.events, _event("run_started", "running", detail)],
                "error": None,
            }
        )
        return self.store.save(updated)

    def _complete(self, record: RunRecord, result: DurableExecutionResult, started: float) -> DurableAgentAskResponse:
        duration_ms = (record.timing.duration_ms or 0) + _elapsed_ms(started)
        if result.status == "waiting_for_approval":
            updated = record.model_copy(
                update={
                    "status": "waiting_for_approval",
                    "agent_run_id": result.native_response.thread_id,
                    "conversation_id": result.compatibility_response.conversation_id,
                    "timing": record.timing.model_copy(update={"duration_ms": duration_ms}),
                    "events": [
                        *record.events,
                        _event("run_waiting_for_approval", "waiting_for_approval", "DeepAgents Graph 已在写入前暂停。"),
                    ],
                }
            )
        else:
            timing = RunTiming(started_at=record.timing.started_at, finished_at=_now(), duration_ms=duration_ms)
            updated = record.model_copy(
                update={
                    "status": "succeeded",
                    "agent_run_id": result.native_response.thread_id,
                    "conversation_id": result.compatibility_response.conversation_id,
                    "timing": timing,
                    "metrics": _build_metrics(result.compatibility_response, timing),
                    "events": [*record.events, _event("run_succeeded", "succeeded", "V3.17 Durable Memory Tool Loop 已执行完成。")],
                }
            )
        self.store.save(updated)
        response = DurableAgentAskResponse(
            run=updated,
            agent_response=result.compatibility_response,
            deep_agent_response=result.native_response,
            approval=result.approval,
        )
        self.store.save_artifacts(updated.run_id, result.native_response.artifacts)
        self.store.save_response(response)
        return response

    def _failed(self, record: RunRecord, exc: Exception, started: float) -> DurableAgentAskResponse:
        timing = RunTiming(
            started_at=record.timing.started_at,
            finished_at=_now(),
            duration_ms=(record.timing.duration_ms or 0) + _elapsed_ms(started),
        )
        updated = record.model_copy(
            update={
                "status": "failed",
                "timing": timing,
                "error": RunError(error_type=type(exc).__name__, message=_safe_error_message(exc), retryable=False),
                "events": [*record.events, _event("run_failed", "failed", "V3.17 Durable Agent 调用异常结束。")],
            }
        )
        self.store.save(updated)
        previous = self.store.get_response(record.run_id)
        response = DurableAgentAskResponse(
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
        return f"Durable Agent 阶段 {payload.get('phase', 'unknown')}：{payload.get('status', 'running')}。"
    if name == "context_summary":
        return "DeepAgents 已压缩旧 Context，并保留可恢复的历史文件引用。"
    if name == "node_finished":
        return f"DeepAgents 节点 {payload.get('node_name', 'unknown')} 已完成。"
    if name == "tool_started":
        return f"开始调用工具 {payload.get('tool_name', 'unknown')}。"
    if name == "tool_finished":
        return f"工具 {payload.get('tool_name', 'unknown')} 调用{payload.get('status', 'completed')}。"
    if name == "answer_delta":
        return "Durable Agent 产生最终可见答案。"
    return f"Durable Agent 产生 {name} 事件。"
