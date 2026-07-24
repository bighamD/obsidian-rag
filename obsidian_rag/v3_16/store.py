from __future__ import annotations

from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from obsidian_rag.v3_15.store import PostgresHitlStore
from obsidian_rag.v3_16.schemas import (
    DeepAgentArtifact,
    DeepAgentAskRequest,
    DeepAgentAskResponse,
)


class PostgresDeepAgentStore(PostgresHitlStore):
    """在 V3.15 Run/HITL 表之上持久保存 V3.16 请求、响应和 Artifact 索引。"""

    def __init__(self, pool, limit: int = 200):
        super().__init__(pool, limit=limit)
        self._initialize_deep_agent_tables()

    def _initialize_deep_agent_tables(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS deep_agent_runs (
                run_id TEXT PRIMARY KEY,
                request_json JSONB NOT NULL,
                response_json JSONB NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_deep_agent_runs_updated ON deep_agent_runs(updated_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS deep_agent_artifacts (
                artifact_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                record_json JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_deep_agent_artifacts_run ON deep_agent_artifacts(run_id)",
        )
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def save_request(self, run_id: str, request: DeepAgentAskRequest) -> None:
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO deep_agent_runs(run_id, request_json, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(run_id) DO UPDATE SET
                        request_json = EXCLUDED.request_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (run_id, Jsonb(request.model_dump(mode="json")), now),
                )

    def get_request(self, run_id: str) -> DeepAgentAskRequest | None:
        row = self._fetchone("SELECT request_json FROM deep_agent_runs WHERE run_id = %s", (run_id,))
        return DeepAgentAskRequest.model_validate(row["request_json"]) if row else None

    def save_response(self, response: DeepAgentAskResponse) -> None:
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE deep_agent_runs
                    SET response_json = %s, updated_at = %s
                    WHERE run_id = %s
                    """,
                    (Jsonb(response.model_dump(mode="json")), now, response.run.run_id),
                )

    def get_response(self, run_id: str) -> DeepAgentAskResponse | None:
        row = self._fetchone("SELECT response_json FROM deep_agent_runs WHERE run_id = %s", (run_id,))
        if not row or row["response_json"] is None:
            return None
        return DeepAgentAskResponse.model_validate(row["response_json"])

    def save_artifacts(self, run_id: str, artifacts: list[DeepAgentArtifact]) -> None:
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("DELETE FROM deep_agent_artifacts WHERE run_id = %s", (run_id,))
                for artifact in artifacts:
                    cursor.execute(
                        """
                        INSERT INTO deep_agent_artifacts(artifact_id, run_id, record_json, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(artifact_id) DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            record_json = EXCLUDED.record_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            artifact.artifact_id,
                            run_id,
                            Jsonb(artifact.model_dump(mode="json")),
                            now,
                        ),
                    )

    def get_artifact(self, artifact_id: str) -> DeepAgentArtifact | None:
        row = self._fetchone(
            "SELECT record_json FROM deep_agent_artifacts WHERE artifact_id = %s",
            (artifact_id,),
        )
        return DeepAgentArtifact.model_validate(row["record_json"]) if row else None

    def ready(self) -> bool:
        if not super().ready():
            return False
        rows = self._fetchall(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name IN ('deep_agent_runs', 'deep_agent_artifacts')
            """
        )
        return {row["table_name"] for row in rows} == {"deep_agent_runs", "deep_agent_artifacts"}
