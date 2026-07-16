import sqlite3

from obsidian_rag.core.memory import SQLiteConversationMemoryStore


def test_conversation_store_lists_recent_first_with_title_and_turn_count(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    store.append_turn("conv_old", "较早的问题", "回答", [], [])
    store.append_turn(
        "conv_new",
        "这是一个很长的用户问题用于验证会话标题会被稳定截断而不是完整展示在侧栏中",
        "回答 1",
        [],
        [],
    )
    store.append_turn("conv_new", "第二个问题", "回答 2", [], [])
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            ("26-07-16 20:00:00", "conv_old"),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            ("26-07-16 21:00:00", "conv_new"),
        )

    conversations = store.list_conversations(limit=10)

    assert [item.conversation_id for item in conversations] == ["conv_new", "conv_old"]
    assert conversations[0].title == "这是一个很长的用户问题用于验证会话标题会被稳定截断而不是..."
    assert conversations[0].turn_count == 2
    assert conversations[1].title == "较早的问题"


def test_conversation_store_delete_removes_conversation_and_associated_turns(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    store = SQLiteConversationMemoryStore(db_path)
    store.append_turn("conv_delete", "问题 1", "回答 1", [], [])
    store.append_turn("conv_delete", "问题 2", "回答 2", [], [])
    store.append_turn("conv_keep", "保留问题", "保留回答", [], [])

    result = store.delete_conversation("conv_delete")

    assert result.deleted is True
    assert result.deleted_turn_count == 2
    assert [item.conversation_id for item in store.list_conversations()] == ["conv_keep"]
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
            ("conv_delete",),
        ).fetchone()[0] == 0


def test_conversation_store_delete_missing_id_changes_nothing(tmp_path):
    store = SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3")
    store.append_turn("conv_keep", "保留问题", "保留回答", [], [])

    result = store.delete_conversation("conv_missing")

    assert result.deleted is False
    assert result.deleted_turn_count == 0
    assert [item.conversation_id for item in store.list_conversations()] == ["conv_keep"]
