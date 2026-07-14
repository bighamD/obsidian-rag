from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from obsidian_rag.v3_8_1.mysql_memory import MySQLConversationMemoryStore


def migrate(source: Path) -> tuple[int, int]:
    if not source.exists():
        raise FileNotFoundError(source)

    store = MySQLConversationMemoryStore()
    connection = store._connect()
    try:
        with sqlite3.connect(source) as sqlite_connection:
            sqlite_connection.row_factory = sqlite3.Row
            conversations = sqlite_connection.execute(
                """
                SELECT conversation_id, created_at, updated_at, summary_text,
                       summary_through_turn_id, summary_updated_at
                FROM conversations
                ORDER BY rowid ASC
                """
            ).fetchall()
            turns = sqlite_connection.execute(
                """
                SELECT rowid AS source_sequence_id, turn_id, conversation_id,
                       user_message, assistant_message, sources_json,
                       tool_calls_json, created_at
                FROM turns
                ORDER BY rowid ASC
                """
            ).fetchall()

        with connection.cursor() as cursor:
            for row in conversations:
                cursor.execute(
                    """
                    INSERT INTO conversations (
                        conversation_id, created_at, updated_at, summary_text,
                        summary_through_turn_id, summary_updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at),
                        summary_text = VALUES(summary_text),
                        summary_through_turn_id = VALUES(summary_through_turn_id),
                        summary_updated_at = VALUES(summary_updated_at)
                    """,
                    tuple(row),
                )
            for row in turns:
                cursor.execute(
                    """
                    INSERT INTO turns (
                        sequence_id, turn_id, conversation_id, user_message,
                        assistant_message, sources_json, tool_calls_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        conversation_id = VALUES(conversation_id),
                        user_message = VALUES(user_message),
                        assistant_message = VALUES(assistant_message),
                        sources_json = VALUES(sources_json),
                        tool_calls_json = VALUES(tool_calls_json),
                        created_at = VALUES(created_at)
                    """,
                    tuple(row),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return len(conversations), len(turns)


def main() -> None:
    parser = argparse.ArgumentParser(description="将 SQLite Conversation Memory 迁移到 MySQL")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path(".rag/v3_10_memory.sqlite3"),
        help="SQLite Memory 文件，默认是当前 V3.10.2 使用的数据库",
    )
    args = parser.parse_args()
    conversations, turns = migrate(args.source)
    print(f"迁移完成：{conversations} 个 conversations，{turns} 条 turns")


if __name__ == "__main__":
    main()
