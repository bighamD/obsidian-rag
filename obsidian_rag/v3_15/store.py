from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from obsidian_rag.core.schemas import StepResult
from obsidian_rag.v3_10.schemas import RunRecord
from obsidian_rag.v3_15.schemas import ApprovalDecision, ApprovalRecord, ApprovalRequest


class PostgresHitlStore:
    """使用 PostgreSQL 持久保存 Run、审批和副作用 Tool 幂等结果。"""

    def __init__(self, pool: ConnectionPool, limit: int = 200):
        # limit：hitl_runs 表只保留最近 N 条，超出的旧 Run 自动清理。
        self.pool = pool
        self.limit = max(1, limit)
        self._initialize()

    def _initialize(self) -> None:
        """建表并做幂等式版本迁移：三张核心表 = Run / 审批 / Tool 幂等结果。"""

        migration_table_sql = """
            CREATE TABLE IF NOT EXISTS hitl_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        migrations = (
            (
                """
                CREATE TABLE IF NOT EXISTS hitl_runs (
                    run_id TEXT PRIMARY KEY,
                    conversation_id TEXT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    record_json JSONB NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_hitl_runs_status_updated ON hitl_runs(status, updated_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_hitl_runs_conversation_updated ON hitl_runs(conversation_id, updated_at DESC)",
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS hitl_approvals (
                    run_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    conversation_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'resolved')),
                    request_json JSONB NOT NULL,
                    decision_json JSONB NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    resolved_at TIMESTAMPTZ NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_hitl_approvals_status_created ON hitl_approvals(status, created_at DESC)",
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS hitl_tool_results (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    result_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_hitl_tool_results_run_step ON hitl_tool_results(run_id, step_id)",
            ),
        )
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(migration_table_sql)
                cursor.execute("SELECT version FROM hitl_schema_migrations")
                applied = {int(row["version"]) for row in cursor.fetchall()}
                # 按 version 顺序执行未应用过的迁移，已应用的跳过（可重复安全执行）。
                for version, statements in enumerate(migrations, start=1):
                    if version in applied:
                        continue
                    for statement in statements:
                        cursor.execute(statement)
                    cursor.execute(
                        "INSERT INTO hitl_schema_migrations(version) VALUES (%s)",
                        (version,),
                    )

    def save(self, record: RunRecord) -> RunRecord:
        """Upsert Run 快照（存在则更新），并按 limit 裁剪最旧记录。"""

        updated_at = _record_updated_at(record)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO hitl_runs(
                        run_id, conversation_id, status, started_at, finished_at,
                        updated_at, record_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(run_id) DO UPDATE SET
                        conversation_id = EXCLUDED.conversation_id,
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        finished_at = EXCLUDED.finished_at,
                        updated_at = EXCLUDED.updated_at,
                        record_json = EXCLUDED.record_json
                    """,
                    (
                        record.run_id,
                        record.conversation_id,
                        record.status,
                        _as_datetime(record.timing.started_at),
                        _as_datetime(record.timing.finished_at),
                        updated_at,
                        Jsonb(record.model_dump(mode="json")),
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM hitl_runs
                    WHERE run_id IN (
                        SELECT run_id FROM hitl_runs
                        ORDER BY updated_at DESC
                        OFFSET %s
                    )
                    """,
                    (self.limit,),
                )
        return record

    def get(self, run_id: str) -> RunRecord | None:
        """按 run_id 读取 Run 快照，不存在返回 None。"""

        row = self._fetchone("SELECT record_json FROM hitl_runs WHERE run_id = %s", (run_id,))
        return RunRecord.model_validate(row["record_json"]) if row else None

    def list_recent(self, limit: int = 20) -> list[RunRecord]:
        """按更新时间倒序列出最近的 Run，供 Console 观察。"""

        rows = self._fetchall(
            "SELECT record_json FROM hitl_runs ORDER BY updated_at DESC LIMIT %s",
            (max(1, limit),),
        )
        return [RunRecord.model_validate(row["record_json"]) for row in rows]

    def save_pending_approval(self, request: ApprovalRequest) -> ApprovalRecord:
        """落库一条 pending 审批；ON CONFLICT DO NOTHING 保证 resume 重放时不覆盖。"""

        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO hitl_approvals(
                        run_id, approval_id, conversation_id, status,
                        request_json, created_at
                    ) VALUES (%s, %s, %s, 'pending', %s, %s)
                    ON CONFLICT(run_id) DO NOTHING
                    """,
                    (
                        request.run_id,
                        request.approval_id,
                        request.conversation_id,
                        Jsonb(request.model_dump(mode="json")),
                        _as_datetime(request.created_at),
                    ),
                )
                cursor.execute("SELECT * FROM hitl_approvals WHERE run_id = %s", (request.run_id,))
                row = cursor.fetchone()
        return _approval_record(row)

    def get_approval(self, run_id: str) -> ApprovalRecord | None:
        """读取该 Run 的审批记录（含请求与决定），不存在返回 None。"""

        row = self._fetchone("SELECT * FROM hitl_approvals WHERE run_id = %s", (run_id,))
        return _approval_record(row) if row else None

    def list_approvals(self, status: str | None = None, limit: int = 50) -> list[ApprovalRecord]:
        """列出审批记录，可按 pending/resolved 过滤，供审批队列展示。"""

        query = "SELECT * FROM hitl_approvals"
        params: list[object] = []
        if status:
            query += " WHERE status = %s"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(max(1, limit))
        return [_approval_record(row) for row in self._fetchall(query, tuple(params))]

    def resolve_approval(self, decision: ApprovalDecision) -> ApprovalRecord:
        """把审批标记为 resolved 并写入决定；FOR UPDATE 行锁避免并发重复处理。"""

        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                # 先加行锁再更新，防止两个 resume 请求同时处理同一审批。
                cursor.execute(
                    "SELECT run_id FROM hitl_approvals WHERE run_id = %s FOR UPDATE",
                    (decision.run_id,),
                )
                if cursor.fetchone() is None:
                    raise KeyError(f"Approval not found: {decision.run_id}")
                cursor.execute(
                    """
                    UPDATE hitl_approvals
                    SET status = 'resolved', decision_json = %s, resolved_at = %s
                    WHERE run_id = %s
                    RETURNING *
                    """,
                    (
                        Jsonb(decision.model_dump(mode="json")),
                        _as_datetime(decision.decided_at),
                        decision.run_id,
                    ),
                )
                row = cursor.fetchone()
        return _approval_record(row)

    def get_tool_result(self, idempotency_key: str) -> StepResult | None:
        """按幂等键查已缓存的 Tool 结果，命中即可跳过重复执行。"""

        row = self._fetchone(
            "SELECT result_json FROM hitl_tool_results WHERE idempotency_key = %s",
            (idempotency_key,),
        )
        return StepResult.model_validate(row["result_json"]) if row else None

    def save_tool_result(
        self,
        idempotency_key: str,
        run_id: str,
        step_id: str,
        result: StepResult,
        created_at: str,
    ) -> None:
        """写入 Tool 幂等结果；ON CONFLICT DO NOTHING 确保同键只保存首次成功结果。"""

        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO hitl_tool_results(
                        idempotency_key, run_id, step_id, result_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(idempotency_key) DO NOTHING
                    """,
                    (
                        idempotency_key,
                        run_id,
                        step_id,
                        Jsonb(result.model_dump(mode="json")),
                        _as_datetime(created_at),
                    ),
                )

    def ready(self) -> bool:
        """探活：三张核心表都存在才算 runtime store 就绪。"""

        rows = self._fetchall(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name IN ('hitl_runs', 'hitl_approvals', 'hitl_tool_results')
            """
        )
        return {row["table_name"] for row in rows} == {
            "hitl_runs",
            "hitl_approvals",
            "hitl_tool_results",
        }

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """从连接池取连接执行查询，返回单行 dict（row_factory=dict_row）。"""

        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """从连接池取连接执行查询，返回全部行。"""

        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def _approval_record(row: dict[str, Any]) -> ApprovalRecord:
    """把 hitl_approvals 一行数据库记录还原为 ApprovalRecord 领域对象。"""

    decision = row["decision_json"]
    return ApprovalRecord(
        request=ApprovalRequest.model_validate(row["request_json"]),
        status=row["status"],
        decision=ApprovalDecision.model_validate(decision) if decision else None,
        resolved_at=_to_iso(row["resolved_at"]),
    )


def _record_updated_at(record: RunRecord) -> datetime:
    """取 Run 的最新时间点作为 updated_at：优先 finished_at，其次末条事件，最后 started_at。"""

    value = record.timing.finished_at or (
        record.events[-1].occurred_at if record.events else record.timing.started_at
    )
    return _as_datetime(value)


def _as_datetime(value: str | datetime | None) -> datetime | None:
    """把 ISO 字符串或 datetime 统一转为带 UTC 时区的 datetime，供 TIMESTAMPTZ 列使用。"""

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _to_iso(value: str | datetime | None) -> str | None:
    """把数据库返回的 datetime 统一转成 ISO 字符串，供 Pydantic/JSON 使用。"""

    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)
