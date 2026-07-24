from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from deepagents.backends import BackendProtocol
from deepagents.backends.protocol import (
    EditResult,
    FileData,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GlobResult,
    GrepMatch,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)

from obsidian_rag.core.sandbox import SandboxRuntime


class DeepAgentsSandboxBackend(BackendProtocol):
    """把 DeepAgents 文件工具限制在一个 Core Sandbox Run Workspace 内。

    DeepAgents 使用 `/artifacts/foo.md` 形式的虚拟绝对路径；Core Sandbox 只接收
    相对路径。所有转换最终仍经过现有 path_guard，并拒绝 Symlink 和目录逃逸。
    """

    def __init__(self, runtime: SandboxRuntime, run_id: str, write_root: str = "/artifacts"):
        self.runtime = runtime
        self.run_id = run_id
        self.write_root = PurePosixPath(write_root).as_posix().rstrip("/") or "/artifacts"

    def ls(self, path: str) -> LsResult:
        try:
            target = self._resolve_directory(path)
            if not target.exists():
                return LsResult(error=f"Path '{path}': path_not_found")
            if not target.is_dir():
                return LsResult(error=f"Path '{path}': not_a_directory")
            entries: list[FileInfo] = []
            for child in sorted(target.iterdir(), key=lambda item: item.name):
                if child.is_symlink():
                    continue
                stat = child.stat()
                virtual_path = self._virtual_path(child)
                entries.append(
                    FileInfo(
                        path=f"{virtual_path}/" if child.is_dir() else virtual_path,
                        is_dir=child.is_dir(),
                        size=0 if child.is_dir() else stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    )
                )
            return LsResult(entries=entries)
        except (OSError, ValueError) as exc:
            return LsResult(error=f"Cannot list '{path}': {exc}")

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        try:
            relative = self._relative_path(file_path)
            payload = self.runtime.read_file(self.run_id, relative)
            content = str(payload["content"])
            lines = content.splitlines(keepends=True)
            if offset >= len(lines) and lines:
                return ReadResult(error=f"Line offset {offset} exceeds file length ({len(lines)} lines)")
            selected = "".join(lines[max(0, offset) : max(0, offset) + max(1, limit)])
            return ReadResult(file_data=FileData(content=selected, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return ReadResult(error=f"Error reading file '{file_path}': {exc}")

    def write(self, file_path: str, content: str) -> WriteResult:
        try:
            self._require_artifact_path(file_path)
            relative = self._relative_path(file_path)
            _, target = self.runtime.workspaces.resolve(self.run_id, relative)
            if target.exists():
                if target.is_file() and target.read_text(encoding="utf-8") == content:
                    return WriteResult(path=file_path)
                return WriteResult(
                    error=(
                        f"Cannot write to {file_path} because it already exists with different content. "
                        "Read it and use edit_file, or choose a new artifact path."
                    )
                )
            self.runtime.write_file(self.run_id, relative, content)
            return WriteResult(path=file_path)
        except (OSError, UnicodeError, ValueError) as exc:
            return WriteResult(error=f"Error writing file '{file_path}': {exc}")

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        try:
            self._require_artifact_path(file_path)
            if old_string == new_string:
                return EditResult(error="old_string and new_string must be different")
            relative = self._relative_path(file_path)
            payload = self.runtime.read_file(self.run_id, relative)
            content = str(payload["content"])
            occurrences = content.count(old_string)
            if occurrences == 0:
                return EditResult(error=f"String not found in {file_path}", occurrences=0)
            if not replace_all and occurrences != 1:
                return EditResult(
                    error=f"String appears {occurrences} times in {file_path}; set replace_all=true or provide a unique string.",
                    occurrences=occurrences,
                )
            updated = content.replace(old_string, new_string, -1 if replace_all else 1)
            self.runtime.write_file(self.run_id, relative, updated)
            return EditResult(path=file_path, occurrences=occurrences if replace_all else 1)
        except (OSError, UnicodeError, ValueError) as exc:
            return EditResult(error=f"Error editing file '{file_path}': {exc}")

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        try:
            if ".." in PurePosixPath(pattern).parts:
                raise ValueError("Glob pattern 不允许包含 '..'。")
            root = self._resolve_directory(path or "/")
            matches: list[FileInfo] = []
            for item in root.rglob(pattern.lstrip("/")):
                if not item.is_file() or item.is_symlink():
                    continue
                stat = item.stat()
                matches.append(
                    FileInfo(
                        path=self._virtual_path(item),
                        is_dir=False,
                        size=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    )
                )
            return GlobResult(matches=sorted(matches, key=lambda item: item["path"]))
        except (OSError, ValueError) as exc:
            return GlobResult(error=f"Error globbing '{pattern}': {exc}", matches=[])

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        try:
            root = self._resolve_directory(path or "/")
            matches: list[GrepMatch] = []
            candidates = [root] if root.is_file() else root.rglob("*")
            for item in candidates:
                if not item.is_file() or item.is_symlink():
                    continue
                relative = self._workspace_relative(item)
                if glob and not PurePosixPath(relative).match(glob):
                    continue
                try:
                    lines = item.read_text(encoding="utf-8").splitlines()
                except UnicodeDecodeError:
                    continue
                for line_number, line in enumerate(lines, start=1):
                    if pattern in line:
                        matches.append(GrepMatch(path=f"/{relative}", line=line_number, text=line))
                        if len(matches) >= 200:
                            return GrepResult(error="结果超过 200 条，已截断。", matches=matches)
            return GrepResult(matches=matches)
        except (OSError, ValueError) as exc:
            return GrepResult(error=f"Error grepping '{pattern}': {exc}", matches=[])

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for file_path, content in files:
            try:
                self._require_artifact_path(file_path)
                if len(content) > self.runtime.backend.profile.max_file_bytes:
                    raise ValueError("文件超过 Sandbox 单文件大小上限。")
                relative = self._relative_path(file_path)
                _, target = self.runtime.workspaces.resolve(self.run_id, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                responses.append(FileUploadResponse(path=file_path, error=None))
            except (OSError, ValueError) as exc:
                responses.append(FileUploadResponse(path=file_path, error=str(exc)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for file_path in paths:
            try:
                relative = self._relative_path(file_path)
                _, target = self.runtime.workspaces.resolve(self.run_id, relative)
                if not target.exists():
                    responses.append(FileDownloadResponse(path=file_path, content=None, error="file_not_found"))
                elif target.is_dir():
                    responses.append(FileDownloadResponse(path=file_path, content=None, error="is_directory"))
                else:
                    responses.append(FileDownloadResponse(path=file_path, content=target.read_bytes(), error=None))
            except (OSError, ValueError) as exc:
                responses.append(FileDownloadResponse(path=file_path, content=None, error=str(exc)))
        return responses

    def _require_artifact_path(self, path: str) -> None:
        normalized = PurePosixPath(path).as_posix()
        if normalized != self.write_root and not normalized.startswith(f"{self.write_root}/"):
            raise ValueError(f"V3.16 只允许写入 {self.write_root}/ 下的 Artifact。")

    def _relative_path(self, path: str) -> str:
        normalized = PurePosixPath(path).as_posix()
        if not normalized.startswith("/"):
            raise ValueError("DeepAgents Backend path 必须是以 '/' 开头的虚拟绝对路径。")
        parts = PurePosixPath(normalized).parts[1:]
        if not parts or any(part in {"", ".", "..", "~"} for part in parts):
            raise ValueError("DeepAgents Backend path 包含非法目录片段。")
        return PurePosixPath(*parts).as_posix()

    def _resolve_directory(self, path: str) -> Path:
        if path == "/":
            workspace = self.runtime.workspaces.get_or_create(self.run_id)
            return Path(workspace.host_path)
        relative = self._relative_path(path)
        _, target = self.runtime.workspaces.resolve(self.run_id, relative)
        return target

    def _workspace_root(self) -> Path:
        workspace = self.runtime.workspaces.get_or_create(self.run_id)
        return Path(workspace.host_path).resolve()

    def _workspace_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self._workspace_root()).as_posix()

    def _virtual_path(self, path: Path) -> str:
        return f"/{self._workspace_relative(path)}"

