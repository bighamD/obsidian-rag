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
from obsidian_rag.v3_10.schemas import (
    AgentAskResponse,
    ProductionAskRequest,
    ProductionAskResponse,
    RunError,
    RunRecord,
    RunStatus,
    RunTiming,
)
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus


# 每次 Run 创建新的 Agent 实例，避免跨请求共享 LangGraph 状态。
AgentFactory = Callable[[], object]


class StreamingAgentRuntimeService:
    """在 V3.10 Production Run 外壳上增加后台执行和 SSE 事件发布。

    同时维护两份状态：
    - run_store：Run 快照，供事后查询和 JSON 响应组装
    - event_bus：实时事件队列，供 SSE 消费
    """

    def __init__(self, agent_factory: AgentFactory, run_store: InMemoryRunStore, event_bus: RunEventBus):
        self.agent_factory = agent_factory
        self.run_store = run_store
        self.event_bus = event_bus

    def ask(self, request: ProductionAskRequest) -> ProductionAskResponse:
        """保留非流式 JSON 契约，供 Swagger、CLI 和兼容调用方使用。"""

        agent = self.agent_factory()
        from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService

        return AgentRuntimeService(agent_service=agent, run_store=self.run_store).ask(request)

    def start_stream(self, request: ProductionAskRequest) -> str:
        """创建 Run 并启动后台线程执行 Agent，立即返回 run_id。

        调用方拿到 run_id 后应通过 stream(run_id) 挂起 SSE 连接消费事件。
        """

        run_id = f"prod_{uuid4().hex[:12]}"
        started_at = _now()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            timing=RunTiming(started_at=started_at),
            events=[_event("run_queued", "queued", "请求已进入 V3.10.2 SSE Run 生命周期。")],
        )
        self.run_store.save(record)
        self.event_bus.create_run(run_id)
        # 先发布 run_queued，确保 SSE 连接建立后能立刻收到第一条事件。
        self.event_bus.publish(
            run_id,
            "run_queued",
            "queued",
            "请求已进入 V3.10.2 SSE Run 生命周期。",
            {"run": record.model_dump(mode="json")},
        )
        # daemon 线程：主请求返回后后台继续执行，不阻塞 HTTP 响应。
        Thread(target=self._run, args=(run_id, request, started_at), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        """返回 SSE 文本迭代器，阻塞直到 run_succeeded 或 run_failed。"""

        return self.event_bus.iter_sse(run_id)

    def _run(self, run_id: str, request: ProductionAskRequest, started_at: str) -> None:
        """后台线程主链路：执行 Agent 并持续更新 Run 状态、发布 SSE 事件。"""

        record = self.run_store.get(run_id)
        if record is None:
            return
        started = perf_counter()
        record = self._append_event(record, "run_started", "running", "开始执行 V3.8.1 Agent，并实时发布节点事件。")

        # 闭包回调：桥接 V3.8.1 Agent 的 event_sink 与 Production Run 外壳。
        # Agent 每完成一个 LangGraph 节点或产生 trace 步骤时调用。
        def publish_agent_event(name: str, payload: dict) -> None:
            nonlocal record
            detail = _agent_event_detail(name, payload)
            if name == "answer_delta":
                self._publish_record_event(record, name, "running", detail, payload)
                return
            record = self._append_event(record, name, "running", detail, {"agent": payload})

        try:
            agent = self.agent_factory()
            agent_response = agent.ask_with_events(request, publish_agent_event)
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
            # run_failed 是终态事件，会驱动 event_bus 结束 SSE 迭代。
            self._publish_record_event(record, "run_failed", "failed", "Agent 调用异常结束。")
            return

        agent_response = AgentAskResponse.model_validate(
            agent_response.model_dump(mode="python") if hasattr(agent_response, "model_dump") else agent_response
        )
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
        # 终态事件的 data.response 携带完整 ProductionAskResponse，前端可在最后一帧拿到答案。
        self._publish_record_event(
            record,
            "run_succeeded",
            "succeeded",
            "V3.8.1 Agent 已返回完整响应。",
            {"response": ProductionAskResponse(run=record, agent_response=agent_response).model_dump(mode="json")},
        )

    def _append_event(
        self,
        record: RunRecord,
        name: str,
        status: RunStatus,
        detail: str,
        data: dict | None = None,
    ) -> RunRecord:
        """双写：同时更新 RunRecord.events 和 SSE 事件总线，保证落盘与实时推送一致。"""

        updated = record.model_copy(update={"status": status, "events": [*record.events, _event(name, status, detail)]})
        self.run_store.save(updated)
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
        """将当前 Run 快照与额外 data 合并后发布到事件总线。

        每条 SSE 事件的 data 都包含完整 run 快照，前端 Run Inspector 可实时刷新。
        额外键如 agent（节点/trace 详情）、response（最终响应）会合并进来。
        """

        payload = {"run": record.model_dump(mode="json"), **(data or {})}
        self.event_bus.publish(record.run_id, name, status, detail, payload)


def _agent_event_detail(name: str, payload: dict) -> str:
    """将 Agent 原始事件 payload 转为面向用户的 detail 文案。"""

    if name == "node_finished":
        duration_ms = payload.get("duration_ms")
        suffix = f"耗时 {duration_ms} ms。" if duration_ms is not None else ""
        return f"LangGraph 节点 {payload.get('node_name', 'unknown')} 已完成，{suffix}"
    if name == "trace_event":
        node_name = payload.get("node_name", "unknown")
        step_type = payload.get("step_type", "event")
        return f"{node_name} 产生 {step_type} 事件。"
    if name == "answer_delta":
        return "Answer LLM 产生最终可见文本增量。"
    if name == "progress":
        return f"Agent 阶段 {payload.get('phase', 'unknown')}：{payload.get('status', 'running')}。"
    return f"Agent 产生 {name} 事件。"
