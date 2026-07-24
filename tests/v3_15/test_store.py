from pathlib import Path

from obsidian_rag.core.permissions import PermissionPrincipal, PermissionReport
from obsidian_rag.v3_15.schemas import ApprovalDecision, ApprovalRequest
from obsidian_rag.v3_15.store import SqliteHitlStore


def test_sqlite_store_persists_pending_and_resolved_approval(tmp_path: Path):
    store = SqliteHitlStore(tmp_path / "runtime.sqlite3")
    request = ApprovalRequest(
        approval_id="approval_run_test",
        run_id="run_test",
        conversation_id="conv_test",
        summary="需要确认。",
        steps=[],
        permission_report=PermissionReport(
            principal=PermissionPrincipal(),
            decisions=[],
            allow_count=0,
            confirm_count=0,
            deny_count=0,
            all_allowed=True,
            summary="测试。",
        ),
        created_at="2026-01-01T00:00:00+00:00",
    )

    pending = store.save_pending_approval(request)
    resolved = store.resolve_approval(
        ApprovalDecision(
            approval_id=request.approval_id,
            run_id=request.run_id,
            action="allow",
            decided_at="2026-01-01T00:01:00+00:00",
        )
    )

    assert pending.status == "pending"
    assert resolved.status == "resolved"
    assert store.get_approval("run_test").decision.action == "allow"
