from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore


def test_sqlite_memory_store_persists_turns_and_applies_window(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")

    for index in range(1, 4):
        store.append_turn(
            conversation_id="conv_food",
            user_message=f"问题 {index}",
            assistant_message=f"回答 {index}",
            sources=[f"KB-{index:03d}"],
            tool_calls=[{"tool": "search_notes", "query": f"query {index}"}],
        )

    snapshot = store.load_snapshot("conv_food", window=2)

    assert snapshot.total_turn_count == 3
    assert snapshot.loaded_turn_count == 2
    assert snapshot.omitted_turn_count == 1
    assert [turn.user_message for turn in snapshot.recent_turns] == ["问题 2", "问题 3"]
    assert snapshot.recent_turns[-1].sources == ["KB-003"]


def test_sqlite_memory_store_isolates_conversations(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    store.append_turn("conv_a", "A 的问题", "A 的回答", [], [])

    snapshot = store.load_snapshot("conv_b", window=3)

    assert snapshot.total_turn_count == 0
    assert snapshot.recent_turns == []
