from __future__ import annotations

from pathlib import Path

from obsidian_rag.core.sandbox.artifacts import ArtifactRegistry
from obsidian_rag.core.sandbox.docker import DockerSandboxBackend
from obsidian_rag.core.sandbox.schemas import SandboxExecutionRequest, SandboxExecutionResult
from obsidian_rag.core.sandbox.workspace import SandboxWorkspaceManager


class SandboxRuntime:
    """统一文件操作、Docker 命令执行和 Artifact 登记。"""

    def __init__(
        self,
        workspaces: SandboxWorkspaceManager,
        backend: DockerSandboxBackend,
        artifacts: ArtifactRegistry,
    ):
        self.workspaces = workspaces
        self.backend = backend
        self.artifacts = artifacts

    def runtime_status(self):
        return self.backend.status()

    def write_file(self, run_id: str, path: str, content: str) -> dict:
        data = content.encode("utf-8")
        if len(data) > self.backend.profile.max_file_bytes:
            raise ValueError(f"文件超过 {self.backend.profile.max_file_bytes} bytes 上限。")
        workspace, target = self.workspaces.resolve(run_id, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "workspace": workspace.model_dump(mode="json"),
            "path": path,
            "size_bytes": len(data),
            "artifacts": [item.model_dump(mode="json") for item in self.artifacts.list_for_run(run_id)],
        }

    def read_file(self, run_id: str, path: str) -> dict:
        workspace, target = self.workspaces.resolve(run_id, path)
        if not target.is_file():
            raise FileNotFoundError(f"Sandbox 文件不存在：{path}")
        data = target.read_bytes()
        if len(data) > self.backend.profile.max_file_bytes:
            raise ValueError(f"文件超过 {self.backend.profile.max_file_bytes} bytes 读取上限。")
        return {
            "workspace": workspace.model_dump(mode="json"),
            "path": path,
            "size_bytes": len(data),
            "content": data.decode("utf-8", errors="replace"),
        }

    def list_files(self, run_id: str) -> dict:
        workspace = self.workspaces.get_or_create(run_id)
        return {
            "workspace": workspace.model_dump(mode="json"),
            "artifacts": [item.model_dump(mode="json") for item in self.artifacts.list_for_run(run_id)],
        }

    def run_command(self, run_id: str, command: str, args: list[str]) -> SandboxExecutionResult:
        workspace = self.workspaces.get_or_create(run_id)
        result = self.backend.execute(
            SandboxExecutionRequest(run_id=run_id, command=command, args=args),
            workspace,
        )
        return result.model_copy(update={"artifacts": self.artifacts.list_for_run(run_id)})

    def artifact_path(self, run_id: str, artifact_id: str) -> tuple[object, Path]:
        return self.artifacts.resolve_artifact(run_id, artifact_id)
