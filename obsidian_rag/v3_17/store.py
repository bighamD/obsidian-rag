from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from psycopg.types.json import Jsonb

from obsidian_rag.v3_16.store import PostgresDeepAgentStore
from obsidian_rag.v3_17.schemas import (
    DurableAgentAskRequest,
    DurableAgentAskResponse,
    DurableConversation,
    DurableConversationDeleteResponse,
    MemoryAuditRecord,
)


class PostgresDurableAgentStore(PostgresDeepAgentStore):
    """V3.16 Run/HITL 之上增加 Conversation Repository 与 Memory Audit。"""

    def __init__(self, pool, limit: int = 200):
        super().__init__(pool, limit=limit)
        self._initialize_durable_tables()

    def _initialize_durable_tables(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS durable_conversations (
                conversation_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                assistant_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'deleted')),
                turn_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_durable_conversations_scope_updated ON durable_conversations(tenant_id, user_id, assistant_id, updated_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS durable_agent_runs (
                run_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                request_json JSONB NOT NULL,
                response_json JSONB NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_durable_agent_runs_conversation ON durable_agent_runs(conversation_id, updated_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS durable_memory_audits (
                audit_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                assistant_id TEXT NOT NULL,
                conversation_id TEXT NULL,
                run_id TEXT NULL,
                memory_id TEXT NULL,
                actor TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_durable_memory_audits_scope_created ON durable_memory_audits(tenant_id, user_id, assistant_id, created_at DESC)",
        )
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def get_or_create_conversation(self, request: DurableAgentAskRequest) -> DurableConversation:
        conversation_id = request.conversation_id or f"conv_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM durable_conversations WHERE conversation_id = %s FOR UPDATE",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                if row is not None:
                    self._assert_scope(row, request.tenant_id, request.user_id, request.assistant_id)
                    if row["status"] != "active":
                        raise ValueError(f"Conversation 已删除：{conversation_id}")
                    cursor.execute(
                        "UPDATE durable_conversations SET turn_count = turn_count + 1, updated_at = %s WHERE conversation_id = %s RETURNING *",
                        (now, conversation_id),
                    )
                    return _conversation(cursor.fetchone())

                thread_id = f"thread_{uuid4().hex}"
                cursor.execute(
                    """
                    INSERT INTO durable_conversations(
                        conversation_id, thread_id, tenant_id, user_id, assistant_id,
                        title, status, turn_count, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'active', 1, %s, %s)
                    RETURNING *
                    """,
                    (
                        conversation_id,
                        thread_id,
                        request.tenant_id,
                        request.user_id,
                        request.assistant_id,
                        _title(request.question),
                        now,
                        now,
                    ),
                )
                return _conversation(cursor.fetchone())

    def get_conversation(
        self,
        conversation_id: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        assistant_id: str | None = None,
    ) -> DurableConversation | None:
        row = self._fetchone(
            "SELECT * FROM durable_conversations WHERE conversation_id = %s AND status = 'active'",
            (conversation_id,),
        )
        if row is None:
            return None
        if tenant_id is not None and user_id is not None and assistant_id is not None:
            self._assert_scope(row, tenant_id, user_id, assistant_id)
        return _conversation(row)

    def list_conversations(
        self,
        tenant_id: str,
        user_id: str,
        assistant_id: str,
        limit: int = 50,
    ) -> list[DurableConversation]:
        rows = self._fetchall(
            """
            SELECT * FROM durable_conversations
            WHERE tenant_id = %s AND user_id = %s AND assistant_id = %s AND status = 'active'
            ORDER BY updated_at DESC LIMIT %s
            """,
            (tenant_id, user_id, assistant_id, max(1, min(limit, 200))),
        )
        return [_conversation(row) for row in rows]

    def delete_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
        user_id: str,
        assistant_id: str,
    ) -> DurableConversationDeleteResponse:
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM durable_conversations WHERE conversation_id = %s FOR UPDATE",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                if row is None or row["status"] == "deleted":
                    return DurableConversationDeleteResponse(
                        conversation_id=conversation_id,
                        thread_id="",
                        deleted=False,
                        deleted_checkpoint_rows=0,
                        long_term_memory_preserved=True,
                    )
                self._assert_scope(row, tenant_id, user_id, assistant_id)
                thread_id = str(row["thread_id"])
                deleted_rows = 0
                for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                    cursor.execute(f"DELETE FROM {table} WHERE thread_id = %s", (thread_id,))
                    deleted_rows += max(0, cursor.rowcount)
                cursor.execute(
                    "UPDATE durable_conversations SET status = 'deleted', updated_at = NOW() WHERE conversation_id = %s",
                    (conversation_id,),
                )
        self.add_audit(
            operation="checkpoint_cleanup",
            tenant_id=tenant_id,
            user_id=user_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            actor="user",
            summary=f"删除 Conversation 并清理 {deleted_rows} 条 Checkpoint 数据；长期 Memory 保留。",
        )
        return DurableConversationDeleteResponse(
            conversation_id=conversation_id,
            thread_id=thread_id,
            deleted=True,
            deleted_checkpoint_rows=deleted_rows,
            long_term_memory_preserved=True,
        )

    def save_request(
        self,
        run_id: str,
        request: DurableAgentAskRequest,
        conversation: DurableConversation | None = None,
    ) -> None:
        conversation = conversation or self.get_conversation(request.conversation_id or "")
        if conversation is None:
            raise KeyError(f"Conversation not found: {request.conversation_id}")
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO durable_agent_runs(run_id, conversation_id, thread_id, request_json, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(run_id) DO UPDATE SET
                        request_json = EXCLUDED.request_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        run_id,
                        conversation.conversation_id,
                        conversation.thread_id,
                        Jsonb(request.model_dump(mode="json")),
                        now,
                    ),
                )

    def get_request(self, run_id: str) -> DurableAgentAskRequest | None:
        row = self._fetchone("SELECT request_json FROM durable_agent_runs WHERE run_id = %s", (run_id,))
        return DurableAgentAskRequest.model_validate(row["request_json"]) if row else None

    def save_response(self, response: DurableAgentAskResponse) -> None:
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE durable_agent_runs SET response_json = %s, updated_at = NOW() WHERE run_id = %s",
                    (Jsonb(response.model_dump(mode="json")), response.run.run_id),
                )

    def get_response(self, run_id: str) -> DurableAgentAskResponse | None:
        row = self._fetchone("SELECT response_json FROM durable_agent_runs WHERE run_id = %s", (run_id,))
        if not row or row["response_json"] is None:
            return None
        return DurableAgentAskResponse.model_validate(row["response_json"])

    def add_audit(
        self,
        *,
        operation: str,
        tenant_id: str,
        user_id: str,
        assistant_id: str,
        actor: str,
        summary: str,
        conversation_id: str | None = None,
        run_id: str | None = None,
        memory_id: str | None = None,
    ) -> MemoryAuditRecord:
        record = MemoryAuditRecord(
            audit_id=f"audit_{uuid4().hex}",
            operation=operation,
            tenant_id=tenant_id,
            user_id=user_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            run_id=run_id,
            memory_id=memory_id,
            actor=actor,
            summary=summary[:500],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO durable_memory_audits(
                        audit_id, operation, tenant_id, user_id, assistant_id,
                        conversation_id, run_id, memory_id, actor, summary, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.audit_id,
                        record.operation,
                        record.tenant_id,
                        record.user_id,
                        record.assistant_id,
                        record.conversation_id,
                        record.run_id,
                        record.memory_id,
                        record.actor,
                        record.summary,
                        datetime.fromisoformat(record.created_at),
                    ),
                )
        return record

    def list_audits(
        self,
        tenant_id: str,
        user_id: str,
        assistant_id: str,
        limit: int = 100,
    ) -> list[MemoryAuditRecord]:
        rows = self._fetchall(
            """
            SELECT * FROM durable_memory_audits
            WHERE tenant_id = %s AND user_id = %s AND assistant_id = %s
            ORDER BY created_at DESC LIMIT %s
            """,
            (tenant_id, user_id, assistant_id, max(1, min(limit, 500))),
        )
        return [_audit(row) for row in rows]

    def ready(self) -> bool:
        if not super().ready():
            return False
        rows = self._fetchall(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name IN ('durable_conversations', 'durable_agent_runs', 'durable_memory_audits')
            """
        )
        return {row["table_name"] for row in rows} == {
            "durable_conversations",
            "durable_agent_runs",
            "durable_memory_audits",
        }

    @staticmethod
    def _assert_scope(row, tenant_id: str, user_id: str, assistant_id: str) -> None:
        actual = (str(row["tenant_id"]), str(row["user_id"]), str(row["assistant_id"]))
        expected = (tenant_id, user_id, assistant_id)
        if actual != expected:
            raise PermissionError("Conversation 不属于当前 tenant/user/assistant scope。")


def _conversation(row) -> DurableConversation:
    return DurableConversation(
        conversation_id=str(row["conversation_id"]),
        thread_id=str(row["thread_id"]),
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        assistant_id=str(row["assistant_id"]),
        title=str(row["title"]),
        status=str(row["status"]),
        turn_count=int(row["turn_count"]),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def _audit(row) -> MemoryAuditRecord:
    return MemoryAuditRecord(
        audit_id=str(row["audit_id"]),
        operation=str(row["operation"]),
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        assistant_id=str(row["assistant_id"]),
        conversation_id=row["conversation_id"],
        run_id=row["run_id"],
        memory_id=row["memory_id"],
        actor=str(row["actor"]),
        summary=str(row["summary"]),
        created_at=row["created_at"].isoformat(),
    )


def _title(question: str) -> str:
    normalized = " ".join(question.split()) or "未命名会话"
    return normalized if len(normalized) <= 60 else f"{normalized[:60]}..."

