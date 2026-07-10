from obsidian_rag.v3_8_1.compaction import ConversationCompactor
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore


class FakeSummaryClient:
    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return "用户持续询问食品安全，重点关注生鸡肉处理和厨房清洁。"


def _append_turns(store, count: int, conversation_id: str = "conv_food") -> None:
    for index in range(1, count + 1):
        store.append_turn(
            conversation_id=conversation_id,
            user_message=f"问题 {index}",
            assistant_message=f"回答 {index}",
            sources=[f"KB-{index:03d}"],
            tool_calls=[],
        )


def test_compactor_summarizes_old_turns_and_keeps_recent_raw_turns(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    _append_turns(store, 5)
    client = FakeSummaryClient()
    compactor = ConversationCompactor(memory_store=store, chat_client=client)

    result = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=2,
        trigger_tokens=10000,
    )
    snapshot = store.load_snapshot("conv_food", window=2)

    assert result.compacted is True
    assert result.summarized_turn_count == 3
    assert result.preserved_turn_count == 2
    assert result.summary_through_turn_id is not None
    assert snapshot.summary_text == "用户持续询问食品安全，重点关注生鸡肉处理和厨房清洁。"
    assert [turn.user_message for turn in snapshot.recent_turns] == ["问题 4", "问题 5"]
    assert snapshot.total_turn_count == 5
    assert "问题 1" in client.messages[0][1]["content"]
    assert "问题 3" in client.messages[0][1]["content"]


def test_compactor_rolls_previous_summary_into_next_summary(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    _append_turns(store, 4)
    client = FakeSummaryClient()
    compactor = ConversationCompactor(memory_store=store, chat_client=client)

    first = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=2,
        trigger_tokens=10000,
    )
    _append_turns(store, 2, conversation_id="conv_food")
    second = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=2,
        trigger_tokens=10000,
    )

    assert first.compacted is True
    assert second.compacted is True
    assert second.summarized_turn_count == 2
    assert "existing_summary" in client.messages[-1][1]["content"]
    assert "用户持续询问食品安全" in client.messages[-1][1]["content"]


def test_compactor_skips_when_threshold_is_not_reached(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    _append_turns(store, 3)
    compactor = ConversationCompactor(memory_store=store, chat_client=FakeSummaryClient())

    result = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=3,
        trigger_tokens=10000,
    )

    assert result.compacted is False
    assert result.attempted is False
    assert result.candidate_turn_count == 1
    assert "未达到" in result.reason


def test_compactor_does_not_initialize_llm_before_threshold(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    _append_turns(store, 3)

    def fail_if_called():
        raise AssertionError("LLM factory should stay lazy")

    compactor = ConversationCompactor(memory_store=store, chat_client_factory=fail_if_called)
    result = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=3,
        trigger_tokens=10000,
    )

    assert result.compacted is False
    assert result.attempted is False


def test_force_compaction_ignores_threshold(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    _append_turns(store, 3)
    compactor = ConversationCompactor(memory_store=store, chat_client=FakeSummaryClient())

    result = compactor.compact(
        conversation_id="conv_food",
        keep_recent_turns=2,
        trigger_turns=99,
        trigger_tokens=99999,
        force=True,
    )

    assert result.attempted is True
    assert result.compacted is True
    assert result.summarized_turn_count == 1
