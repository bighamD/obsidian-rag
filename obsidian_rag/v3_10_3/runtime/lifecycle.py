from __future__ import annotations

from threading import Thread
from uuid import uuid4

from obsidian_rag.v3_10.schemas import RunStatus
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_3.agent.service import AdvancedAgentService
from obsidian_rag.v3_10_3.schemas import AdvancedAskRequest, AdvancedAskResponse


class AdvancedStreamingRuntimeService:
    """把 Advanced Graph 的多模式 stream 转换为现有 EventBus/SSE 事件。"""

    def __init__(self, agent_service: AdvancedAgentService, event_bus: RunEventBus):
        self.agent_service = agent_service
        self.event_bus = event_bus

    def ask(self, request: AdvancedAskRequest) -> AdvancedAskResponse:
        return self.agent_service.ask(request)

    def start_stream(self, request: AdvancedAskRequest) -> str:
        run_id = f"adv_{uuid4().hex[:12]}"
        self.event_bus.create_run(run_id)
        self.event_bus.publish(
            run_id,
            "run_queued",
            "queued",
            "V3.10.3 Advanced Run 已进入队列。",
            {"run_id": run_id},
        )
        Thread(target=self._run, args=(run_id, request), daemon=True).start()
        return run_id

    def stream(self, run_id: str):
        return self.event_bus.iter_sse(run_id)

    def _run(self, run_id: str, request: AdvancedAskRequest) -> None:
        self._publish(run_id, "run_started", "running", "开始执行 V3.10.3 Advanced Graph。")
        try:
            for item in self.agent_service.stream_events(request, run_id):
                if item["name"] == "final_response":
                    self._publish(
                        run_id,
                        "run_succeeded",
                        "succeeded",
                        item["detail"],
                        item["data"],
                    )
                    return
                self._publish(run_id, item["name"], "running", item["detail"], item.get("data"))
        except Exception as exc:
            self._publish(
                run_id,
                "run_failed",
                "failed",
                "V3.10.3 Advanced Graph 执行失败。",
                {"error_type": type(exc).__name__, "message": str(exc)[:500]},
            )

    def _publish(
        self,
        run_id: str,
        name: str,
        status: RunStatus,
        detail: str,
        data: dict | None = None,
    ) -> None:
        self.event_bus.publish(run_id, name, status, detail, data or {})

