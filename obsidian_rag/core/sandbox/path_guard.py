from __future__ import annotations

from pathlib import Path


def resolve_workspace_path(root: Path, relative_path: str) -> Path:
    """解析相对 Workspace 路径，并拒绝绝对路径、逃逸和 Symlink 穿透。

    这是所有落盘路径的安全收口：任何把外部输入映射到磁盘的操作都必须过它。
    """

    candidate_text = relative_path.strip()
    if not candidate_text:
        raise ValueError("Sandbox path 不能为空。")
    candidate = Path(candidate_text)
    # 拒绝 /etc/passwd 之类的绝对路径。
    if candidate.is_absolute():
        raise ValueError("Sandbox 不允许绝对路径。")
    # 拒绝 ".." / "." 等片段，从源头挡住 ../../ 目录逃逸。
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("Sandbox path 包含非法目录片段。")
    root = root.resolve()
    resolved = (root / candidate).resolve(strict=False)
    # 解析后必须仍落在 root 内（防御符号解析后产生的逃逸）。
    if resolved != root and root not in resolved.parents:
        raise ValueError("Sandbox path 试图逃逸 Workspace。")
    # 逐级检查父目录，防止中途经过 Symlink 指向 Workspace 外。
    current = root
    for part in candidate.parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Sandbox path 不允许经过 Symlink。")
    # 目标本身也不能是 Symlink，避免直接写/读到外部文件。
    if resolved.exists() and resolved.is_symlink():
        raise ValueError("Sandbox path 不允许指向 Symlink。")
    return resolved
