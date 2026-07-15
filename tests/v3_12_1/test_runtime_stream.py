import json

from obsidian_rag.core.agent.service import AgentService
from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import ProductionAskRequest
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService

class FakePlanner:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(goal="回答", steps=[PlanStep(id="s1", kind="search", query=request.question)]),
            graph_path=[],
            trace=[],
        )


class FakeRetrieval:
    def search(self, query, top_k=5, mode="hybrid", filters=None, collection=None):
        return [
            SearchResult(
                chunk=TextChunk(text="熟剩菜冷藏三至四天。", metadata={"source": "food.md", "chunk_id": "F-1"}),
                score=0.9,
            )
        ]


class StreamingChat:
    def complete(self, messages):
        return "fallback"

    def stream(self, messages):
        yield "熟剩菜冷藏"
        yield "三至四天。"


def test_v3_10_2_runtime_forwards_answer_delta_and_terminal_response(tmp_path):
    def factory():
        return AgentService(
            retrieval_service=FakeRetrieval(),
            planner_service=FakePlanner(),
            chat_client=StreamingChat(),
            memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
        )

    runtime = StreamingAgentRuntimeService(factory, InMemoryRunStore(), RunEventBus())
    run_id = runtime.start_stream(ProductionAskRequest(question="剩菜多久？"))
    frames = list(runtime.stream(run_id))
    event_names = [
        next(item.split(":", 1)[1].strip() for item in frame.splitlines() if item.startswith("event:"))
        for frame in frames
    ]
    payloads = [json.loads(line.split("data:", 1)[1].strip()) for line in frames]

    assert event_names.count("answer_delta") == 2
    assert event_names[-1] == "run_succeeded"
    assert payloads[-1]["data"]["response"]["agent_response"]["answer"] == "熟剩菜冷藏三至四天。"
