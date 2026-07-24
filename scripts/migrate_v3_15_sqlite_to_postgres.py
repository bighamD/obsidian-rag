from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from obsidian_rag.core.schemas import StepResult
from obsidian_rag.v3_10.schemas import RunRecord
from obsidian_rag.v3_15.dependencies import CHECKPOINT_TYPES
from obsidian_rag.v3_15.postgres import PostgresStateSettings, create_postgres_pool
from obsidian_rag.v3_15.schemas import ApprovalDecision, ApprovalRequest
from obsidian_rag.v3_15.store import PostgresHitlStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将 V3.15 SQLite Runtime 与 LangGraph Checkpoint 迁移到 PostgreSQL。"
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path(".rag-state/v3_15"),
        help="旧 V3.15 SQLite 目录。",
    )
    args = parser.parse_args()

    load_dotenv(".env")
    settings = PostgresStateSettings.from_env()
    pool = create_postgres_pool(settings)
    try:
        serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
        target_saver = PostgresSaver(pool, serde=serde)
        target_saver.setup()
        target_store = PostgresHitlStore(pool)

        runtime_counts = migrate_runtime(args.state_root / "runtime.sqlite3", target_store)
        checkpoint_count, write_count = migrate_checkpoints(
            args.state_root / "checkpoints.sqlite3",
            target_saver,
            serde,
        )
    finally:
        pool.close()

    print(f"PostgreSQL: {settings.display_location()} schema={settings.schema}")
    print(
        "Runtime migrated: "
        f"runs={runtime_counts['runs']} approvals={runtime_counts['approvals']} "
        f"tool_results={runtime_counts['tool_results']}"
    )
    print(f"Checkpoint migrated: checkpoints={checkpoint_count} pending_writes={write_count}")
    return 0


def migrate_runtime(path: Path, target: PostgresHitlStore) -> dict[str, int]:
    counts = {"runs": 0, "approvals": 0, "tool_results": 0}
    if not path.exists():
        return counts

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        for row in connection.execute("SELECT record_json FROM hitl_runs ORDER BY updated_at"):
            target.save(RunRecord.model_validate_json(row["record_json"]))
            counts["runs"] += 1

        for row in connection.execute("SELECT * FROM hitl_approvals ORDER BY created_at"):
            request = ApprovalRequest.model_validate_json(row["request_json"])
            target.save_pending_approval(request)
            if row["decision_json"]:
                target.resolve_approval(ApprovalDecision.model_validate_json(row["decision_json"]))
            counts["approvals"] += 1

        for row in connection.execute("SELECT * FROM hitl_tool_results ORDER BY created_at"):
            target.save_tool_result(
                row["idempotency_key"],
                row["run_id"],
                row["step_id"],
                StepResult.model_validate_json(row["result_json"]),
                row["created_at"],
            )
            counts["tool_results"] += 1
    finally:
        connection.close()
    return counts


def migrate_checkpoints(
    path: Path,
    target: PostgresSaver,
    serde: JsonPlusSerializer,
) -> tuple[int, int]:
    if not path.exists():
        return 0, 0

    connection = sqlite3.connect(path, check_same_thread=False)
    source = SqliteSaver(connection, serde=serde)
    checkpoint_count = 0
    write_count = 0
    try:
        entries = list(source.list(None))
        for entry in reversed(entries):
            current = entry.config["configurable"]
            parent_id = (
                entry.parent_config["configurable"].get("checkpoint_id")
                if entry.parent_config
                else None
            )
            put_config = {
                "configurable": {
                    "thread_id": str(current["thread_id"]),
                    "checkpoint_ns": str(current.get("checkpoint_ns", "")),
                }
            }
            if parent_id:
                put_config["configurable"]["checkpoint_id"] = str(parent_id)
            saved_config = target.put(
                put_config,
                entry.checkpoint,
                entry.metadata,
                entry.checkpoint.get("channel_versions", {}),
            )
            checkpoint_count += 1

            grouped: dict[str, list[tuple[str, object]]] = defaultdict(list)
            for task_id, channel, value in entry.pending_writes or []:
                grouped[str(task_id)].append((str(channel), value))
            for task_id, writes in grouped.items():
                target.put_writes(saved_config, writes, task_id)
                write_count += len(writes)
    finally:
        connection.close()
    return checkpoint_count, write_count


if __name__ == "__main__":
    raise SystemExit(main())
