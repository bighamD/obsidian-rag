from __future__ import annotations

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_1.schemas import CoreAskRequest, CoreStreamConfigResponse


class CoreRuntimeLearningService:
    """V3.12.1 教学门面：复用公共 Core 和现有 Production/SSE Runtime。"""

    def __init__(self, runtime: StreamingAgentRuntimeService):
        self.runtime = runtime

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
            hidden_reasoning_exposed=False,
        )
