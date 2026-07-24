from __future__ import annotations

from pathlib import Path

from obsidian_rag.core.sandbox import SandboxRuntime
from obsidian_rag.v3_16.schemas import DeepAgentArtifact


def project_artifacts(runtime: SandboxRuntime, run_id: str) -> list[DeepAgentArtifact]:
    """扫描 Core Workspace，并为每个 Artifact 增加稳定下载 URL。"""

    return [
        DeepAgentArtifact(
            **record.model_dump(mode="python"),
            download_url=f"/artifacts/{record.artifact_id}/download",
        )
        for record in runtime.artifacts.list_for_run(run_id)
    ]


def resolve_artifact(runtime: SandboxRuntime, store, artifact_id: str) -> tuple[DeepAgentArtifact, Path]:
    """通过 PostgreSQL 中的 artifact_id -> run_id 映射安全定位下载文件。"""

    owner = store.get_artifact(artifact_id)
    if owner is None:
        raise KeyError(f"未知 Artifact: {artifact_id}")
    record, path = runtime.artifact_path(owner.run_id, artifact_id)
    return DeepAgentArtifact(
        **record.model_dump(mode="python"),
        download_url=f"/artifacts/{record.artifact_id}/download",
    ), path

