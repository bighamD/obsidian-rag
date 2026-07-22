from __future__ import annotations

import re
from pathlib import Path

from obsidian_rag.core.sandbox.path_guard import resolve_workspace_path
from obsidian_rag.core.sandbox.schemas import SandboxWorkspace


class SandboxWorkspaceManager:
    """创建并管理每个 Agent Run 的受控 Workspace。"""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, run_id: str) -> SandboxWorkspace:
        workspace_id = _safe_workspace_id(run_id)
        path = self.root / workspace_id / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return SandboxWorkspace(workspace_id=workspace_id, host_path=str(path))

    def resolve(self, run_id: str, relative_path: str) -> tuple[SandboxWorkspace, Path]:
        workspace = self.get_or_create(run_id)
        return workspace, resolve_workspace_path(Path(workspace.host_path), relative_path)


def _safe_workspace_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    if not normalized:
        raise ValueError("run_id 无法生成有效 Workspace ID。")
    return normalized[:120]
