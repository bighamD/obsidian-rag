from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from obsidian_rag.core.sandbox.path_guard import resolve_workspace_path
from obsidian_rag.core.sandbox.schemas import ArtifactRecord
from obsidian_rag.core.sandbox.workspace import SandboxWorkspaceManager


class ArtifactRegistry:
    """扫描受控 Workspace 并生成可验证、可下载的 Artifact 记录。"""

    def __init__(self, workspaces: SandboxWorkspaceManager):
        self.workspaces = workspaces

    def list_for_run(self, run_id: str) -> list[ArtifactRecord]:
        workspace = self.workspaces.get_or_create(run_id)
        root = Path(workspace.host_path)
        records = []
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
            records.append(_record(run_id, root, path))
        return records

    def resolve_artifact(self, run_id: str, artifact_id: str) -> tuple[ArtifactRecord, Path]:
        for record in self.list_for_run(run_id):
            if record.artifact_id == artifact_id:
                workspace = self.workspaces.get_or_create(run_id)
                return record, resolve_workspace_path(Path(workspace.host_path), record.relative_path)
        raise KeyError(f"未知 Artifact: {artifact_id}")


def _record(run_id: str, root: Path, path: Path) -> ArtifactRecord:
    relative_path = path.relative_to(root).as_posix()
    digest_builder = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()
    size_bytes = path.stat().st_size
    artifact_key = hashlib.sha256(f"{run_id}:{relative_path}".encode()).hexdigest()[:16]
    return ArtifactRecord(
        artifact_id=f"artifact_{artifact_key}",
        run_id=run_id,
        relative_path=relative_path,
        mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        size_bytes=size_bytes,
        sha256=digest,
        created_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
    )
