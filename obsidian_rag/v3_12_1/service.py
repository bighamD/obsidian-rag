from __future__ import annotations

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_1.schemas import CoreAskRequest, CoreStreamConfigResponse


class CoreRuntimeLearningService:
    """V3.12.1 教学门面：复用公共 Core 和现有 Production/SSE Runtime。"""

    def __init__(
        self,
        runtime: StreamingAgentRuntimeService,
        *,
        reasoning_stream_enabled: bool = False,
        reasoning_effort: str = "medium",
    ):
        self.runtime = runtime
        self.reasoning_stream_enabled = reasoning_stream_enabled
        self.reasoning_effort = reasoning_effort

    def ask(self, request: CoreAskRequest) -> ProductionAskResponse:
        return self.runtime.ask(request)

    def start_stream(self, request: CoreAskRequest) -> str:
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def config(self) -> CoreStreamConfigResponse:
        return CoreStreamConfigResponse(
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            answer_delta_enabled=True,
            reasoning_delta_enabled=self.reasoning_stream_enabled,
            reasoning_effort=self.reasoning_effort if self.reasoning_stream_enabled else None,
            hidden_reasoning_exposed=self.reasoning_stream_enabled,
        )
