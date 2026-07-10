import sqlite3

from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore


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


def test_memory_turn_created_at_is_displayed_in_china_timezone(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    store = SQLiteConversationMemoryStore(db_path)
    write_result = store.append_turn("conv_food", "问题", "回答", [], [])

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE turns SET created_at = ? WHERE turn_id = ?",
            ("2026-07-10T06:28:41.347667+00:00", write_result.turn_id),
        )

    snapshot = store.load_snapshot("conv_food", window=1)

    assert snapshot.recent_turns[0].created_at == "26-07-10 14:28:41"


def test_memory_store_persists_conversation_summary_without_deleting_turns(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    first = store.append_turn("conv_food", "问题 1", "回答 1", [], [])
    store.append_turn("conv_food", "问题 2", "回答 2", [], [])

    store.save_summary(
        conversation_id="conv_food",
        summary_text="此前讨论了问题 1。",
        summary_through_turn_id=first.turn_id,
    )
    snapshot = store.load_snapshot("conv_food", window=1)

    assert snapshot.summary_text == "此前讨论了问题 1。"
    assert snapshot.summary_through_turn_id == first.turn_id
    assert snapshot.total_turn_count == 2
    assert snapshot.recent_turns[0].user_message == "问题 2"
