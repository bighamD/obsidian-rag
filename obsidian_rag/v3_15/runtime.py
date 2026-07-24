from __future__ import annotations

from threading import Thread
from time import perf_counter
from uuid import uuid4

from obsidian_rag.v3_10.runtime.lifecycle import _build_metrics, _elapsed_ms, _event, _now, _safe_error_message
from obsidian_rag.v3_10.schemas import RunError, RunRecord, RunTiming
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_15.schemas import (
    ApprovalDecisionInput,
    HitlAskRequest,
    HitlAskResponse,
    HitlExecutionResult,
)
from obsidian_rag.v3_15.store import PostgresHitlStore


class HitlRuntimeService:
    """管理可暂停 Run，并把 Checkpoint 状态映射为 JSON/SSE 生命周期。"""

    def __init__(self, agent_factory, store: PostgresHitlStore, event_bus: RunEventBus):
        # agent_factory：每次调用现造一个 HitlAgentService（线程安全考量）。
        # store：Run/审批/幂等的持久化。event_bus：把后台线程事件转成 SSE。
        self.agent_factory = agent_factory
        self.store = store
        self.event_bus = event_bus

    def ask(self, request: HitlAskRequest) -> HitlAskResponse:
        """同步首次执行：新建 Run 记录 → begin() → 完成/失败落库并返回。"""

        run_id = f"hitl_{uuid4().hex[:12]}"
        record = self._new_record(run_id)
        record = self._running(record, "开始执行 V3.15 Agent。")
        started = perf_counter()
        try:
            result = self.agent_factory().begin(request, run_id)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def resume(self, run_id: str, decision: ApprovalDecisionInput) -> HitlAskResponse:
        """同步恢复：Run 必须处于 waiting_for_approval，携带人工决定继续执行。"""

        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "waiting_for_approval":
            raise ValueError(f"Run is not waiting for approval: {run_id}")
        record = self._running(record, f"收到人工决定 {decision.action}，开始从 Checkpoint 恢复。")
        started = perf_counter()
        try:
            result = self.agent_factory().resume(run_id, decision)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def recover(self, run_id: str) -> HitlAskResponse:
        """同步恢复失败 Run：Run 必须为 failed，从最近 Checkpoint 重跑失败节点。"""

        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "failed":
            raise ValueError(f"Run is not failed: {run_id}")
        record = self._running(record, "从最近持久 Checkpoint 重试失败节点。")
        started = perf_counter()
        try:
            result = self.agent_factory().recover(run_id)
        except Exception as exc:
            return self._failed(record, exc, started)
        return self._complete(record, result, started)

    def start_stream(self, request: HitlAskRequest) -> str:
        """SSE 首次执行：建 Run、起后台线程跑 begin，立即返回 run_id 供订阅。"""

        run_id = f"hitl_{uuid4().hex[:12]}"
        record = self._new_record(run_id)
        self.event_bus.create_run(run_id)
        self._publish(record, "run_queued", "queued", "请求已进入 V3.15 持久恢复生命周期。")
        # daemon 线程执行 Agent，主线程立刻返回 run_id，由 stream() 消费事件。
        Thread(target=self._run_stream, args=(run_id, request, None), daemon=True).start()
        return run_id

    def start_resume_stream(self, run_id: str, decision: ApprovalDecisionInput) -> str:
        """SSE 恢复审批：校验状态后起后台线程走 resume 分支。"""

        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "waiting_for_approval":
            raise ValueError(f"Run is not waiting for approval: {run_id}")
        self.event_bus.create_run(run_id)
        Thread(target=self._run_stream, args=(run_id, None, decision), daemon=True).start()
        return run_id

    def start_recovery_stream(self, run_id: str) -> str:
        """SSE 恢复失败 Run：校验为 failed 后起后台线程走 recover 分支。"""

        record = self.store.get(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        if record.status != "failed":
            raise ValueError(f"Run is not failed: {run_id}")
        self.event_bus.create_run(run_id)
        Thread(target=self._run_recovery_stream, args=(run_id,), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        """把该 Run 的事件流转成 SSE 迭代器，供 StreamingResponse 消费。"""

        return self.event_bus.iter_sse(run_id)

    def _run_stream(
        self,
        run_id: str,
        request: HitlAskRequest | None,
        decision: ApprovalDecisionInput | None,
    ) -> None:
        """后台线程主体：request 非空走 begin，否则携 decision 走 resume；全程发事件。"""

        record = self.store.get(run_id)
        if record is None:
            return
        detail = "开始执行 V3.15 Agent。" if request is not None else f"收到人工决定 {decision.action}，从 Checkpoint 恢复。"
        record = self._running(record, detail)
        self._publish(record, "run_started" if request is not None else "run_resumed", "running", detail)
        started = perf_counter()

        # event_sink 被 Agent 内部逐节点调用，转发为 SSE 事件。
        def event_sink(name: str, payload: dict) -> None:
            current = self.store.get(run_id) or record
            self._publish(current, name, "running", _agent_event_detail(name, payload), {"agent": payload})

        try:
            agent = self.agent_factory()
            result = agent.begin(request, run_id, event_sink) if request is not None else agent.resume(run_id, decision, event_sink)
        except Exception as exc:
            response = self._failed(record, exc, started)
            self._publish(response.run, "run_failed", "failed", "Agent 调用异常结束。", {"response": response.model_dump(mode="json")})
            return
        response = self._complete(record, result, started)
        event_name = "run_waiting_for_approval" if result.status == "waiting_for_approval" else "run_succeeded"
        detail = "Graph 已持久化并暂停，等待人工审批。" if result.status == "waiting_for_approval" else "Graph 已恢复并执行完成。"
        self._publish(response.run, event_name, response.run.status, detail, {"response": response.model_dump(mode="json")})

    def _run_recovery_stream(self, run_id: str) -> None:
        """后台线程主体：从 Checkpoint 重跑失败节点，全程发事件。"""

        record = self.store.get(run_id)
        if record is None:
            return
        detail = "从最近持久 Checkpoint 重试失败节点。"
        record = self._running(record, detail)
        self._publish(record, "run_recovering", "running", detail)
        started = perf_counter()

        def event_sink(name: str, payload: dict) -> None:
            current = self.store.get(run_id) or record
            self._publish(current, name, "running", _agent_event_detail(name, payload), {"agent": payload})

        try:
            result = self.agent_factory().recover(run_id, event_sink)
        except Exception as exc:
            response = self._failed(record, exc, started)
            self._publish(response.run, "run_failed", "failed", "恢复执行仍然失败。", {"response": response.model_dump(mode="json")})
            return
        response = self._complete(record, result, started)
        self._publish(
            response.run,
            "run_succeeded",
            "succeeded",
            "失败节点已从 Checkpoint 恢复并执行完成。",
            {"response": response.model_dump(mode="json")},
        )

    def _new_record(self, run_id: str) -> RunRecord:
        """创建并持久化 queued 状态的 Run 快照。"""

        record = RunRecord(
            run_id=run_id,
            status="queued",
            timing=RunTiming(started_at=_now()),
            events=[_event("run_queued", "queued", "请求已进入 V3.15 持久恢复生命周期。")],
        )
        return self.store.save(record)

    def _running(self, record: RunRecord, detail: str) -> RunRecord:
        """把 Run 置为 running 并追加一条事件后落库。"""

        updated = record.model_copy(
            update={
                "status": "running",
                "events": [*record.events, _event("run_started", "running", detail)],
                "error": None,
            }
        )
        return self.store.save(updated)

    def _complete(self, record: RunRecord, result: HitlExecutionResult, started: float) -> HitlAskResponse:
        """执行结束的收尾：据结果是暂停还是成功，写不同终态并累加耗时。"""

        duration_ms = (record.timing.duration_ms or 0) + _elapsed_ms(started)
        # 暂停等待审批：Run 终态记 waiting_for_approval，可随后 resume。
        if result.status == "waiting_for_approval":
            updated = record.model_copy(
                update={
                    "status": "waiting_for_approval",
                    "agent_run_id": result.run_id,
                    "conversation_id": result.response.conversation_id,
                    "timing": record.timing.model_copy(update={"duration_ms": duration_ms}),
                    "events": [
                        *record.events,
                        _event("run_waiting_for_approval", "waiting_for_approval", "Graph 已持久化并暂停，等待人工审批。"),
                    ],
                }
            )
        else:
            finished_at = _now()
            timing = RunTiming(
                started_at=record.timing.started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
            )
            updated = record.model_copy(
                update={
                    "status": "succeeded",
                    "agent_run_id": result.run_id,
                    "conversation_id": result.response.conversation_id,
                    "timing": timing,
                    "metrics": _build_metrics(result.response, timing),
                    "events": [*record.events, _event("run_succeeded", "succeeded", "Graph 已恢复并执行完成。")],
                }
            )
        self.store.save(updated)
        return HitlAskResponse(run=updated, agent_response=result.response, approval=result.approval)

    def _failed(self, record: RunRecord, exc: Exception, started: float) -> HitlAskResponse:
        """异常收尾：记 failed 终态；因有 Checkpoint，之后可用 recover 重试。"""

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
                "events": [*record.events, _event("run_failed", "failed", "Agent 调用异常结束。")],
            }
        )
        self.store.save(updated)
        return HitlAskResponse(run=updated, agent_response=None, approval=self.store.get_approval(record.run_id))

    def _publish(self, record: RunRecord, name: str, status, detail: str, data: dict | None = None) -> None:
        """统一向 event_bus 推事件，附带最新 Run 快照供前端渲染。"""

        self.event_bus.publish(
            record.run_id,
            name,
            status,
            detail,
            {"run": record.model_dump(mode="json"), **(data or {})},
        )


def _agent_event_detail(name: str, payload: dict) -> str:
    """把 Agent 内部事件名映射成给前端展示的中文描述文本。"""

    if name == "progress":
        return f"Agent 阶段 {payload.get('phase', 'unknown')}：{payload.get('status', 'running')}。"
    if name == "node_finished":
        return f"LangGraph 节点 {payload.get('node_name', 'unknown')} 已完成。"
    if name == "tool_started":
        return f"开始调用工具 {payload.get('tool_name', 'unknown')}。"
    if name == "tool_finished":
        return f"工具 {payload.get('tool_name', 'unknown')} 调用{payload.get('status', 'completed')}。"
    if name == "answer_delta":
        return "Answer LLM 产生最终可见文本增量。"
    return f"Agent 产生 {name} 事件。"
