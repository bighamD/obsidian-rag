from pathlib import Path

from obsidian_rag.core.agent.service import AgentService
from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.llm import ChatStreamDelta
from obsidian_rag.core.schemas import AgentAskRequest, Plan, PlanResponse, PlanStep
from obsidian_rag.schema import SearchResult, TextChunk


class FakePlanner:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="回答食品安全问题",
                steps=[PlanStep(id="s1", kind="search", query="剩菜 保存")],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrieval:
    def search(self, query, top_k=5, mode="hybrid", filters=None, collection=None):
        return [
            SearchResult(
                chunk=TextChunk(
                    text="熟剩菜冷藏通常建议三至四天内食用。",
                    metadata={"source": "food.md", "chunk_id": "FOOD-001"},
                ),
                score=0.9,
            )
        ]

    def collection_name(self, collection=None):
        return collection or "food_safety"


class StreamingChat:
    def complete(self, messages):
        return "不应调用 complete"

    def stream(self, messages):
        yield "熟剩菜冷藏"
        yield "三至四天。"


class ReasoningStreamingChat:
    def complete(self, messages):
        return "不应调用 complete"

    def stream(self, messages):
        yield ChatStreamDelta(kind="reasoning", text="先确认冷藏条件。")
        yield ChatStreamDelta(kind="content", text="熟剩菜冷藏")
        yield ChatStreamDelta(kind="reasoning", text="再补充时间范围。")
        yield ChatStreamDelta(kind="content", text="三至四天。")


class FallbackChat:
    def stream(self, messages):
        raise RuntimeError("stream unavailable")

    def complete(self, messages):
        return "回退后的完整答案。"


def _service(tmp_path: Path, chat) -> AgentService:
    return AgentService(
        retrieval_service=FakeRetrieval(),
        planner_service=FakePlanner(),
        chat_client=chat,
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )


def test_core_streams_visible_answer_and_keeps_final_response(tmp_path: Path):
    events = []

    response = _service(tmp_path, StreamingChat()).ask_with_events(
        AgentAskRequest(question="剩菜可以保存多久？", collection="food_safety"),
        lambda name, payload: events.append((name, payload)),
    )

    deltas = [payload for name, payload in events if name == "answer_delta"]
    assert [item["sequence"] for item in deltas] == [1, 2]
    assert len({item["message_id"] for item in deltas}) == 1
    assert "".join(item["delta"] for item in deltas) == response.answer
    assert response.answer_stream.mode == "stream"
    assert response.answer_stream.llm_ttft_ms is not None
    assert "reasoning_content" not in str(deltas)


def test_core_publishes_stable_progress_with_retrieval_facts(tmp_path: Path):
    events = []

    _service(tmp_path, StreamingChat()).ask_with_events(
        AgentAskRequest(question="剩菜可以保存多久？", collection="food_safety"),
        lambda name, payload: events.append((name, payload)),
    )

    progress = [payload for name, payload in events if name == "progress"]
    planning = [(item["phase"], item["status"]) for item in progress if item["phase"] == "planning"]
    retrieval = [item for item in progress if item["phase"] == "retrieval"]

    assert planning == [("planning", "running"), ("planning", "completed")]
    assert [(item["status"], item["collection"]) for item in retrieval] == [
        ("running", "food_safety"),
        ("completed", "food_safety"),
    ]
    assert retrieval[-1]["result_count"] == 1
    assert all("正在" not in str(item) and "已找到" not in str(item) for item in progress)


def test_core_streams_reasoning_separately_from_final_answer(tmp_path: Path):
    events = []

    response = _service(tmp_path, ReasoningStreamingChat()).ask_with_events(
        AgentAskRequest(question="剩菜可以保存多久？"),
        lambda name, payload: events.append((name, payload)),
    )

    reasoning = [payload for name, payload in events if name == "reasoning_delta"]
    answer = [payload for name, payload in events if name == "answer_delta"]
    assert [item["sequence"] for item in reasoning] == [1, 2]
    assert "".join(item["delta"] for item in reasoning) == "先确认冷藏条件。再补充时间范围。"
    assert "".join(item["delta"] for item in answer) == response.answer == "熟剩菜冷藏三至四天。"
    assert response.answer_stream.reasoning_character_count == len("先确认冷藏条件。再补充时间范围。")
    assert response.answer_stream.llm_reasoning_ttft_ms is not None
    assert "先确认冷藏条件" not in response.answer


def test_core_falls_back_before_first_chunk(tmp_path: Path):
    response = _service(tmp_path, FallbackChat()).ask_with_events(
        AgentAskRequest(question="剩菜可以保存多久？"),
        lambda _name, _payload: None,
    )

    assert response.answer == "回退后的完整答案。"
    assert response.answer_stream.mode == "fallback"
    assert response.answer_stream.llm_ttft_ms is None


def test_core_and_current_main_do_not_depend_on_v3_8_1():
    root = Path(__file__).resolve().parents[2]
    for path in (root / "obsidian_rag" / "core").rglob("*.py"):
        assert "obsidian_rag.v3_" not in path.read_text(encoding="utf-8"), path

    current_main_files = [
        root / "obsidian_rag/v3_10/dependencies.py",
        root / "obsidian_rag/v3_10/schemas.py",
        root / "obsidian_rag/v3_10_2/dependencies.py",
        root / "obsidian_rag/v3_11/agent/service.py",
        root / "obsidian_rag/v3_11/schemas.py",
    ]
    for path in current_main_files:
        assert "obsidian_rag.v3_8_1" not in path.read_text(encoding="utf-8"), path
