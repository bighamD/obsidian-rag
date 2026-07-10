from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_8.agent.service import AgentService
from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_8.schemas import AgentAskRequest


class FakePlannerService:
    def __init__(self):
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return PlanResponse(
            question=request.question,
            plan=Plan(goal="回答食品安全问题", steps=[PlanStep(id="s1", kind="search", query="厨房 清洁")]),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [
            SearchResult(
                chunk=TextChunk(
                    text="处理生肉后要清洁台面并洗手。",
                    metadata={"source": "food.md", "chunk_id": "KB-073", "topic": "厨房清洁"},
                ),
                score=0.88,
            )
        ]


class FakeChatClient:
    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return "处理生肉后要清洁台面并洗手。"


def test_v3_8_second_turn_reads_memory_for_planner_and_answer_context(tmp_path):
    memory_store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    planner = FakePlannerService()
    chat = FakeChatClient()
    service = AgentService(
        retrieval_service=FakeRetrievalService(),
        planner_service=planner,
        chat_client=chat,
        memory_store=memory_store,
    )

    first = service.ask(AgentAskRequest(question="生鸡肉要不要洗？", memory_window=3))
    second = service.ask(
        AgentAskRequest(
            question="那处理完厨房怎么清洁？",
            conversation_id=first.conversation_id,
            memory_window=3,
        )
    )

    assert first.conversation_id.startswith("conv_")
    assert first.memory_snapshot.loaded_turn_count == 0
    assert first.memory_write.saved is True
    assert second.conversation_id == first.conversation_id
    assert second.memory_snapshot.loaded_turn_count == 1
    assert second.memory_snapshot.recent_turns[0].user_message == "生鸡肉要不要洗？"
    assert "生鸡肉要不要洗？" in planner.requests[-1].question
    assert "那处理完厨房怎么清洁？" in planner.requests[-1].question
    assert "生鸡肉要不要洗？" in chat.messages[-1][1]["content"]
    assert second.graph_path == [
        "load_memory",
        "planner",
        "execute_steps",
        "evidence_check",
        "build_context",
        "synthesize_answer",
        "save_memory",
    ]
