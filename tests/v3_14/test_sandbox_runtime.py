from pathlib import Path

import pytest

from obsidian_rag.core.sandbox import ArtifactRegistry, DockerSandboxBackend, SandboxProfile, SandboxRuntime, SandboxWorkspaceManager
from obsidian_rag.core.sandbox.path_guard import resolve_workspace_path


def test_path_guard_rejects_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        resolve_workspace_path(tmp_path, "../secret.txt")


def test_workspace_file_write_registers_artifact(tmp_path: Path):
    workspaces = SandboxWorkspaceManager(tmp_path)
    backend = DockerSandboxBackend(SandboxProfile(), tmp_path)
    artifacts = ArtifactRegistry(workspaces)
    runtime = SandboxRuntime(workspaces, backend, artifacts)

    result = runtime.write_file("run_test", "output/report.md", "hello")

    assert result["path"] == "output/report.md"
    assert result["artifacts"][0]["relative_path"] == "output/report.md"
