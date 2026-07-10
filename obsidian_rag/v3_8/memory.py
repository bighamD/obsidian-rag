from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from obsidian_rag.v3_8.schemas import MemorySnapshot, MemoryTurn, MemoryWriteResult


class SQLiteConversationMemoryStore:
    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def load_snapshot(self, conversation_id: str, window: int = 3) -> MemorySnapshot:
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            rows = []
            if window > 0:
                rows = connection.execute(
                    """
                    SELECT turn_id, conversation_id, user_message, assistant_message,
                           sources_json, tool_calls_json, created_at
                    FROM turns
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT ?
                    """,
                    (conversation_id, window),
                ).fetchall()

        recent_turns = [_memory_turn_from_row(row) for row in reversed(rows)]
        return MemorySnapshot(
            conversation_id=conversation_id,
            window=window,
            recent_turns=recent_turns,
            total_turn_count=total,
            loaded_turn_count=len(recent_turns),
            omitted_turn_count=max(0, total - len(recent_turns)),
        )

    def append_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        sources: list[str],
        tool_calls: list[dict[str, object]],
    ) -> MemoryWriteResult:
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        created_at = _china_time_text(datetime.now(timezone.utc).isoformat())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (conversation_id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (conversation_id, created_at, created_at),
            )
            connection.execute(
                """
                INSERT INTO turns (
                    turn_id, conversation_id, user_message, assistant_message,
                    sources_json, tool_calls_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    conversation_id,
                    user_message,
                    assistant_message,
                    json.dumps(sources, ensure_ascii=False),
                    json.dumps(tool_calls, ensure_ascii=False),
                    created_at,
                ),
            )
        return MemoryWriteResult(conversation_id=conversation_id, turn_id=turn_id, saved=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_message TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    tool_calls_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_conversation_created ON turns(conversation_id, created_at)"
            )
            _migrate_timestamps_to_china_time(connection)


def default_memory_db_path() -> Path:
    return Path(os.getenv("RAG_MEMORY_DB_PATH", ".rag/v3_8_memory.sqlite3"))


def _memory_turn_from_row(row: sqlite3.Row) -> MemoryTurn:
    return MemoryTurn(
        turn_id=str(row["turn_id"]),
        conversation_id=str(row["conversation_id"]),
        user_message=str(row["user_message"]),
        assistant_message=str(row["assistant_message"]),
        sources=_load_json_list(row["sources_json"]),
        tool_calls=_load_json_list(row["tool_calls_json"]),
        created_at=str(row["created_at"]),
    )


def _load_json_list(value: str) -> list:
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _migrate_timestamps_to_china_time(connection: sqlite3.Connection) -> None:
    for table, id_column, columns in (
        ("conversations", "conversation_id", ("created_at", "updated_at")),
        ("turns", "turn_id", ("created_at",)),
    ):
        selected_columns = ", ".join((id_column, *columns))
        for row in connection.execute(f"SELECT {selected_columns} FROM {table}").fetchall():
            updates = {column: _china_time_text(str(row[column])) for column in columns}
            assignments = ", ".join(f"{column} = ?" for column in columns)
            connection.execute(
                f"UPDATE {table} SET {assignments} WHERE {id_column} = ?",
                (*updates.values(), row[id_column]),
            )


def _china_time_text(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%y-%m-%d %H:%M:%S")
