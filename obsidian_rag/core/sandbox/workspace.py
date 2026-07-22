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
        """按 run_id 获取（不存在则创建）该 Run 的独立 Workspace 目录。"""

        workspace_id = _safe_workspace_id(run_id)
        path = self.root / workspace_id / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return SandboxWorkspace(workspace_id=workspace_id, host_path=str(path))

    def resolve(self, run_id: str, relative_path: str) -> tuple[SandboxWorkspace, Path]:
        """定位 Workspace，并把相对路径经 path_guard 解析成安全的绝对路径。"""

        workspace = self.get_or_create(run_id)
        return workspace, resolve_workspace_path(Path(workspace.host_path), relative_path)


def _safe_workspace_id(value: str) -> str:
    """把 run_id 规范化为文件系统安全的目录名，防止 run_id 本身被用来目录穿越。"""

    # 非字母数字下划线连字符一律替换为 _，再去掉首尾 _。
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    if not normalized:
        raise ValueError("run_id 无法生成有效 Workspace ID。")
    return normalized[:120]
