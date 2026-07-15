from __future__ import annotations

from threading import Thread
from time import perf_counter
from typing import Callable
from uuid import uuid4

from obsidian_rag.v3_10.runtime.lifecycle import (
    _build_metrics,
    _elapsed_ms,
    _event,
    _now,
    _safe_error_message,
)
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import RunError, RunRecord, RunStatus, RunTiming
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_11.schemas import SkillAgentResponse, SkillAskRequest, SkillProductionAskResponse


AgentFactory = Callable[[], object]


class SkillRuntimeService:
    """为 V3.11 Skill Agent 提供 JSON Run 和 SSE Run 两种入口。"""

    def __init__(self, agent_factory: AgentFactory, run_store: InMemoryRunStore, event_bus: RunEventBus):
        self.agent_factory = agent_factory
        self.run_store = run_store
        self.event_bus = event_bus

    def ask(self, request: SkillAskRequest) -> SkillProductionAskResponse:
        """同步执行 Skill Agent，供 Swagger JSON 和 CLI 使用。"""

        run_id, started_at, record = self._create_run()
        started = perf_counter()
        record = self._append_event(record, "run_started", "running", "开始执行 V3.11 Skill Agent。")

        event_record = {"value": record}

        def publish_event(name: str, payload: dict) -> None:
            if name == "answer_delta":
                return
            event_record["value"] = self._append_event(
                event_record["value"],
                name,
                "running",
                _event_detail(name, payload),
                {"skill_agent": payload},
                publish=False,
            )

        try:
            result = self.agent_factory().ask_with_events(request, publish_event)
        except Exception as exc:
            record = event_record["value"]
            record = self._failed_record(record, started_at, started, exc)
            return SkillProductionAskResponse(run=record, skill_result=None)
        record = event_record["value"]
        record = self._succeeded_record(record, started_at, started, result)
        return SkillProductionAskResponse(run=record, skill_result=result)

    def start_stream(self, request: SkillAskRequest) -> str:
        """创建后台 Run，并返回供 `/agent/ask/stream` 消费的 run_id。"""

        run_id, started_at, record = self._create_run()
        self.event_bus.create_run(run_id)
        self._publish_record_event(record, "run_queued", "queued", "请求已进入 V3.11 SSE Run 生命周期。")
        Thread(target=self._run_stream, args=(run_id, request, started_at), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        """阻塞消费事件直到 run_succeeded 或 run_failed。"""

        return self.event_bus.iter_sse(run_id)

    def _run_stream(self, run_id: str, request: SkillAskRequest, started_at: str) -> None:
        record = self.run_store.get(run_id)
        if record is None:
            return
        started = perf_counter()
        record = self._append_event(record, "run_started", "running", "开始执行 V3.11 Skill Agent。")
        self._publish_record_event(record, "run_started", "running", "开始执行 V3.11 Skill Agent。")

        def publish_event(name: str, payload: dict) -> None:
            nonlocal record
            if name == "answer_delta":
                self._publish_record_event(
                    record,
                    name,
                    "running",
                    "Answer LLM 产生最终可见文本增量。",
                    payload,
                )
                return
            record = self._append_event(
                record,
                name,
                "running",
                _event_detail(name, payload),
                {"skill_agent": payload},
            )

        try:
            result = self.agent_factory().ask_with_events(request, publish_event)
        except Exception as exc:
            record = self._failed_record(record, started_at, started, exc)
            self._publish_record_event(record, "run_failed", "failed", "Skill Agent 调用异常结束。")
            return
        record = self._succeeded_record(record, started_at, started, result)
        self._publish_record_event(
            record,
            "run_succeeded",
            "succeeded",
            "V3.11 Skill Agent 已返回完整响应。",
            {"response": SkillProductionAskResponse(run=record, skill_result=result).model_dump(mode="json")},
        )

    def _create_run(self) -> tuple[str, str, RunRecord]:
        run_id = f"prod_{uuid4().hex[:12]}"
        started_at = _now()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            timing=RunTiming(started_at=started_at),
            events=[_event("run_queued", "queued", "请求已进入 V3.11 Skill Run 生命周期。")],
        )
        self.run_store.save(record)
        return run_id, started_at, record

    def _succeeded_record(self, record: RunRecord, started_at: str, started: float, result: SkillAgentResponse) -> RunRecord:
        timing = RunTiming(
            started_at=started_at,
            finished_at=_now(),
            duration_ms=_elapsed_ms(started),
        )
        updated = record.model_copy(
            update={
                "status": "succeeded",
                "agent_run_id": result.agent_response.run_id,
                "conversation_id": result.agent_response.conversation_id,
                "timing": timing,
                "metrics": _build_metrics(result.agent_response, timing),
                "events": [*record.events, _event("run_succeeded", "succeeded", "V3.11 Skill Agent 已返回完整响应。")],
            }
        )
        self.run_store.save(updated)
        return updated

    def _failed_record(self, record: RunRecord, started_at: str, started: float, exc: Exception) -> RunRecord:
        updated = record.model_copy(
            update={
                "status": "failed",
                "timing": RunTiming(
                    started_at=started_at,
                    finished_at=_now(),
                    duration_ms=_elapsed_ms(started),
                ),
                "error": RunError(
                    error_type=type(exc).__name__,
                    message=_safe_error_message(exc),
                    retryable=False,
                ),
                "events": [*record.events, _event("run_failed", "failed", "V3.11 Skill Agent 调用异常结束。")],
            }
        )
        self.run_store.save(updated)
        return updated

    def _append_event(
        self,
        record: RunRecord,
        name: str,
        status: RunStatus,
        detail: str,
        data: dict | None = None,
        publish: bool = True,
    ) -> RunRecord:
        updated = record.model_copy(update={"status": status, "events": [*record.events, _event(name, status, detail)]})
        self.run_store.save(updated)
        if publish and (name.startswith("skill_") or name in {"node_finished", "trace_event", "answer_delta"}):
            self._publish_record_event(updated, name, status, detail, data)
        return updated

    def _publish_record_event(
        self,
        record: RunRecord,
        name: str,
        status: RunStatus,
        detail: str,
        data: dict | None = None,
    ) -> None:
        payload = {"run": record.model_dump(mode="json"), **(data or {})}
        self.event_bus.publish(record.run_id, name, status, detail, payload)


def _event_detail(name: str, payload: dict) -> str:
    if name == "node_finished":
        duration_ms = payload.get("duration_ms")
        suffix = f"耗时 {duration_ms} ms。" if duration_ms is not None else ""
        return f"LangGraph 节点 {payload.get('node_name', 'unknown')} 已完成，{suffix}"
    if name == "trace_event":
        return f"Agent 节点 {payload.get('node_name', 'unknown')} 产生 {payload.get('step_type', 'event')} 事件。"
    return f"Skill 节点 {payload.get('node_name', name)}：{payload.get('reason', '已完成')}"
