from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

import pymysql
from pymysql.connections import Connection

from obsidian_rag.core.memory import (
    ConversationDeleteResult,
    ConversationSummary,
    MemoryCompactionCandidate,
    _china_time_text,
    _conversation_summary_from_row,
)
from obsidian_rag.core.schemas import MemorySnapshot, MemoryTurn, MemoryWriteResult


@dataclass(frozen=True)
class MySQLMemorySettings:
    """MySQL Memory 连接配置；默认面向本机开发环境。"""

    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "obsidian_rag"
    unix_socket: str | None = None

    @classmethod
    def from_env(cls) -> "MySQLMemorySettings":
        return cls(
            host=os.getenv("RAG_MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("RAG_MYSQL_PORT", "3306")),
            user=os.getenv("RAG_MYSQL_USER", "root"),
            password=os.getenv("RAG_MYSQL_PASSWORD", ""),
            database=os.getenv("RAG_MYSQL_DATABASE", "obsidian_rag"),
            unix_socket=os.getenv("RAG_MYSQL_SOCKET") or None,
        )


class MySQLConversationMemoryStore:
    """使用 MySQL 持久化原始 Turn 和滚动摘要。

    `sequence_id` 是跨会话表内的自增顺序，用来替代 SQLite `rowid`，
    确保 Memory Window 和 compaction 能稳定判断 Turn 的先后关系。
    """

    def __init__(self, settings: MySQLMemorySettings | None = None):
        self.settings = settings or MySQLMemorySettings.from_env()
        _validate_database_name(self.settings.database)
        self._ensure_database()
        self._initialize()

    def load_snapshot(self, conversation_id: str, window: int = 3) -> MemorySnapshot:
        with self._session() as connection:
            conversation = self._fetchone(
                connection,
                """
                SELECT summary_text, summary_through_turn_id, summary_updated_at
                FROM conversations
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            total = int(
                self._fetchone(
                    connection,
                    "SELECT COUNT(*) AS total FROM turns WHERE conversation_id = %s",
                    (conversation_id,),
                )["total"]
            )
            rows: list[dict[str, Any]] = []
            if window > 0:
                rows = self._fetchall(
                    connection,
                    """
                    SELECT turn_id, conversation_id, user_message, assistant_message,
                           sources_json, tool_calls_json, created_at
                    FROM turns
                    WHERE conversation_id = %s
                    ORDER BY sequence_id DESC
                    LIMIT %s
                    """,
                    (conversation_id, window),
                )

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

    def list_conversations(self, limit: int = 50) -> list[ConversationSummary]:
        with self._session() as connection:
            rows = self._fetchall(
                connection,
                """
                SELECT c.conversation_id, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM turns counted
                        WHERE counted.conversation_id = c.conversation_id) AS turn_count,
                       (SELECT first_turn.user_message FROM turns first_turn
                        WHERE first_turn.conversation_id = c.conversation_id
                        ORDER BY first_turn.sequence_id ASC LIMIT 1) AS first_user_message
                FROM conversations c
                ORDER BY c.updated_at DESC, c.conversation_id DESC
                LIMIT %s
                """,
                (limit,),
            )
        return [_conversation_summary_from_row(row) for row in rows]

    def delete_conversation(self, conversation_id: str) -> ConversationDeleteResult:
        with self._session() as connection:
            conversation = self._fetchone(
                connection,
                "SELECT conversation_id FROM conversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            if conversation is None:
                return ConversationDeleteResult(
                    conversation_id=conversation_id,
                    deleted=False,
                    deleted_turn_count=0,
                )
            turn_count = int(
                self._fetchone(
                    connection,
                    "SELECT COUNT(*) AS total FROM turns WHERE conversation_id = %s",
                    (conversation_id,),
                )["total"]
            )
            self._execute(
                connection,
                "DELETE FROM conversations WHERE conversation_id = %s",
                (conversation_id,),
            )
        return ConversationDeleteResult(
            conversation_id=conversation_id,
            deleted=True,
            deleted_turn_count=turn_count,
        )

    def load_compaction_candidate(
        self,
        conversation_id: str,
        keep_recent_turns: int,
    ) -> MemoryCompactionCandidate:
        with self._session() as connection:
            conversation = self._fetchone(
                connection,
                """
                SELECT summary_text, summary_through_turn_id
                FROM conversations
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
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
            summary_sequence_id = 0
            if summary_through_turn_id:
                marker = self._fetchone(
                    connection,
                    """
                    SELECT sequence_id
                    FROM turns
                    WHERE turn_id = %s AND conversation_id = %s
                    """,
                    (summary_through_turn_id, conversation_id),
                )
                if marker:
                    summary_sequence_id = int(marker["sequence_id"])

            total_turn_count = int(
                self._fetchone(
                    connection,
                    "SELECT COUNT(*) AS total FROM turns WHERE conversation_id = %s",
                    (conversation_id,),
                )["total"]
            )
            unsummarized_count = int(
                self._fetchone(
                    connection,
                    """
                    SELECT COUNT(*) AS total
                    FROM turns
                    WHERE conversation_id = %s AND sequence_id > %s
                    """,
                    (conversation_id, summary_sequence_id),
                )["total"]
            )
            candidate_count = max(0, unsummarized_count - keep_recent_turns)
            rows: list[dict[str, Any]] = []
            if candidate_count > 0:
                rows = self._fetchall(
                    connection,
                    """
                    SELECT turn_id, conversation_id, user_message, assistant_message,
                           sources_json, tool_calls_json, created_at
                    FROM turns
                    WHERE conversation_id = %s AND sequence_id > %s
                    ORDER BY sequence_id ASC
                    LIMIT %s
                    """,
                    (conversation_id, summary_sequence_id, candidate_count),
                )

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
        updated_at = _china_time_text(datetime.now(timezone.utc).isoformat())
        with self._session() as connection:
            self._execute(
                connection,
                """
                UPDATE conversations
                SET summary_text = %s, summary_through_turn_id = %s,
                    summary_updated_at = %s, updated_at = %s
                WHERE conversation_id = %s
                """,
                (summary_text, summary_through_turn_id, updated_at, updated_at, conversation_id),
            )
            if self._fetchone(
                connection,
                "SELECT conversation_id FROM conversations WHERE conversation_id = %s",
                (conversation_id,),
            ) is None:
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
        with self._session() as connection:
            self._execute(
                connection,
                """
                INSERT INTO conversations (conversation_id, created_at, updated_at, summary_text)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE updated_at = %s
                """,
                (conversation_id, created_at, created_at, "", created_at),
            )
            self._execute(
                connection,
                """
                INSERT INTO turns (
                    turn_id, conversation_id, user_message, assistant_message,
                    sources_json, tool_calls_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
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

    @contextmanager
    def _session(self) -> Iterator[Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self, *, database: str | None = None) -> Connection:
        kwargs: dict[str, Any] = {
            "host": self.settings.host,
            "port": self.settings.port,
            "user": self.settings.user,
            "password": self.settings.password,
            "database": database or self.settings.database,
            "charset": "utf8mb4",
            "autocommit": False,
            "cursorclass": pymysql.cursors.DictCursor,
        }
        if self.settings.unix_socket:
            kwargs["unix_socket"] = self.settings.unix_socket
        return pymysql.connect(**kwargs)

    def _ensure_database(self) -> None:
        connection = self._connect(database="mysql")
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.settings.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._session() as connection:
            self._execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id VARCHAR(191) PRIMARY KEY,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL,
                    summary_text LONGTEXT NOT NULL,
                    summary_through_turn_id VARCHAR(64) NULL,
                    summary_updated_at VARCHAR(64) NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            self._execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS turns (
                    sequence_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    turn_id VARCHAR(64) NOT NULL UNIQUE,
                    conversation_id VARCHAR(191) NOT NULL,
                    user_message LONGTEXT NOT NULL,
                    assistant_message LONGTEXT NOT NULL,
                    sources_json LONGTEXT NOT NULL,
                    tool_calls_json LONGTEXT NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    CONSTRAINT fk_turns_conversation
                        FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE,
                    INDEX idx_turns_conversation_sequence (conversation_id, sequence_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )

    @staticmethod
    def _execute(connection: Connection, query: str, params: tuple[Any, ...] = ()):
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor

    @classmethod
    def _fetchone(cls, connection: Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @classmethod
    def _fetchall(cls, connection: Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def _validate_database_name(database: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("RAG_MYSQL_DATABASE 只能包含字母、数字和下划线")


def _memory_turn_from_row(row: dict[str, Any]) -> MemoryTurn:
    return MemoryTurn(
        turn_id=str(row["turn_id"]),
        conversation_id=str(row["conversation_id"]),
        user_message=str(row["user_message"]),
        assistant_message=str(row["assistant_message"]),
        sources=_load_json_list(row["sources_json"]),
        tool_calls=_load_json_list(row["tool_calls_json"]),
        created_at=str(row["created_at"]),
    )


def _load_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
