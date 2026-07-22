from __future__ import annotations

from pathlib import Path


def resolve_workspace_path(root: Path, relative_path: str) -> Path:
    """解析相对 Workspace 路径，并拒绝绝对路径、逃逸和 Symlink 穿透。"""

    candidate_text = relative_path.strip()
    if not candidate_text:
        raise ValueError("Sandbox path 不能为空。")
    candidate = Path(candidate_text)
    if candidate.is_absolute():
        raise ValueError("Sandbox 不允许绝对路径。")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("Sandbox path 包含非法目录片段。")
    root = root.resolve()
    resolved = (root / candidate).resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError("Sandbox path 试图逃逸 Workspace。")
    current = root
    for part in candidate.parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Sandbox path 不允许经过 Symlink。")
    if resolved.exists() and resolved.is_symlink():
        raise ValueError("Sandbox path 不允许指向 Symlink。")
    return resolved
