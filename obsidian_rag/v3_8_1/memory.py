from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from obsidian_rag.v3_8_1.schemas import MemorySnapshot, MemoryTurn, MemoryWriteResult


@dataclass(frozen=True)
class MemoryCompactionCandidate:
    conversation_id: str
    existing_summary: str
    summary_through_turn_id: str | None
    turns_to_summarize: list[MemoryTurn]
    total_turn_count: int
    preserved_turn_count: int


class SQLiteConversationMemoryStore:
    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def load_snapshot(self, conversation_id: str, window: int = 3) -> MemorySnapshot:
        with self._connect() as connection:
            conversation = connection.execute(
                """
                SELECT summary_text, summary_through_turn_id, summary_updated_at
                FROM conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
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
            summary_text=str(conversation["summary_text"] or "") if conversation else "",
            summary_through_turn_id=(
                str(conversation["summary_through_turn_id"])
                if conversation and conversation["summary_through_turn_id"]
                else None
            ),
            summary_updated_at=(
                str(conversation["summary_updated_at"])
                if conversation and conversation["summary_updated_at"]
                else None
            ),
        )

    def load_compaction_candidate(
        self,
        conversation_id: str,
        keep_recent_turns: int,
    ) -> MemoryCompactionCandidate:
        with self._connect() as connection:
            conversation = connection.execute(
                """
                SELECT summary_text, summary_through_turn_id
                FROM conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            if conversation is None:
                return MemoryCompactionCandidate(
                    conversation_id=conversation_id,
                    existing_summary="",
                    summary_through_turn_id=None,
                    turns_to_summarize=[],
                    total_turn_count=0,
                    preserved_turn_count=0,
                )

            summary_through_turn_id = conversation["summary_through_turn_id"]
            summary_rowid = 0
            if summary_through_turn_id:
                marker = connection.execute(
                    "SELECT rowid FROM turns WHERE turn_id = ? AND conversation_id = ?",
                    (summary_through_turn_id, conversation_id),
                ).fetchone()
                if marker:
                    summary_rowid = int(marker[0])

            total_turn_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            unsummarized_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ? AND rowid > ?",
                    (conversation_id, summary_rowid),
                ).fetchone()[0]
            )
            candidate_count = max(0, unsummarized_count - keep_recent_turns)
            rows = []
            if candidate_count > 0:
                rows = connection.execute(
                    """
                    SELECT turn_id, conversation_id, user_message, assistant_message,
                           sources_json, tool_calls_json, created_at
                    FROM turns
                    WHERE conversation_id = ? AND rowid > ?
                    ORDER BY rowid ASC
                    LIMIT ?
                    """,
                    (conversation_id, summary_rowid, candidate_count),
                ).fetchall()

        return MemoryCompactionCandidate(
            conversation_id=conversation_id,
            existing_summary=str(conversation["summary_text"] or ""),
            summary_through_turn_id=(str(summary_through_turn_id) if summary_through_turn_id else None),
            turns_to_summarize=[_memory_turn_from_row(row) for row in rows],
            total_turn_count=total_turn_count,
            preserved_turn_count=min(keep_recent_turns, unsummarized_count),
        )

    def save_summary(
        self,
        conversation_id: str,
        summary_text: str,
        summary_through_turn_id: str,
    ) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET summary_text = ?, summary_through_turn_id = ?,
                    summary_updated_at = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (summary_text, summary_through_turn_id, updated_at, updated_at, conversation_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(conversation_id)

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
                    updated_at TEXT NOT NULL,
                    summary_text TEXT NOT NULL DEFAULT '',
                    summary_through_turn_id TEXT,
                    summary_updated_at TEXT
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
            self._ensure_column(connection, "conversations", "summary_text", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "conversations", "summary_through_turn_id", "TEXT")
            self._ensure_column(connection, "conversations", "summary_updated_at", "TEXT")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            _migrate_timestamps_to_china_time(connection)


def default_memory_db_path() -> Path:
    return Path(os.getenv("RAG_V3_8_1_MEMORY_DB_PATH", ".rag/v3_8_1_memory.sqlite3"))


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
