from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SandboxExecutionStatus = Literal["success", "failed", "timeout", "unavailable"]


class SandboxProfile(BaseModel):
    """Docker Sandbox 的固定隔离与资源限制配置。"""

    name: str = Field(default="locked-python", description="Sandbox Profile 名称。")
    image: str = Field(default="python:3.12-slim", description="执行命令使用的固定 Docker Image。")
    network_disabled: bool = Field(default=True, description="是否通过 network=none 禁止容器网络。")
    read_only_root: bool = Field(default=True, description="容器根文件系统是否只读。")
    timeout_seconds: int = Field(default=15, ge=1, le=120, description="单次命令最长执行时间。")
    max_output_bytes: int = Field(default=131072, ge=1024, le=1048576, description="stdout/stderr 合计上限。")
    max_file_bytes: int = Field(default=1048576, ge=1024, le=10485760, description="单个读写文件大小上限。")
    memory_mb: int = Field(default=256, ge=64, le=2048, description="容器内存限制，单位 MB。")
    cpus: float = Field(default=1.0, gt=0, le=4, description="容器 CPU 上限。")
    pids_limit: int = Field(default=32, ge=8, le=256, description="容器最大进程数。")
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["python", "python3"],
        description="允许在容器中直接执行的程序名；不支持 shell 字符串。",
    )


class SandboxWorkspace(BaseModel):
    """一个 Agent Run 对应的独立 Sandbox Workspace。"""

    workspace_id: str = Field(description="通常等于 Agent run_id 的稳定 Workspace 标识。")
    host_path: str = Field(description="宿主机上的受控 Workspace 路径，仅用于调试。")
    container_path: str = Field(default="/workspace", description="容器内固定挂载路径。")


class ArtifactRecord(BaseModel):
    """Sandbox Workspace 中可下载文件的结构化登记记录。"""

    artifact_id: str = Field(description="Artifact 稳定标识。")
    run_id: str = Field(description="产生该文件的 Agent Run。")
    relative_path: str = Field(description="相对 Workspace 的安全路径。")
    mime_type: str = Field(description="根据文件名推断的 MIME 类型。")
    size_bytes: int = Field(ge=0, description="文件字节大小。")
    sha256: str = Field(description="文件内容 SHA-256。")
    created_at: str = Field(description="登记时间，UTC ISO 8601。")


class SandboxExecutionRequest(BaseModel):
    """在隔离容器中执行一个白名单命令的请求。"""

    run_id: str = Field(min_length=1, description="目标 Workspace 和 Artifact 归属的 Agent Run。")
    command: str = Field(min_length=1, description="白名单程序名，例如 python。")
    args: list[str] = Field(default_factory=list, description="直接传给程序的参数数组，不经过 Shell 解析。")


class SandboxExecutionResult(BaseModel):
    """Docker Sandbox 命令执行结果。"""

    run_id: str = Field(description="关联 Agent Run。")
    workspace: SandboxWorkspace = Field(description="本次命令使用的独立 Workspace。")
    status: SandboxExecutionStatus = Field(description="success、failed、timeout 或 unavailable。")
    command: str = Field(description="实际执行的白名单程序。")
    args: list[str] = Field(description="实际传入的参数数组。")
    exit_code: int | None = Field(default=None, description="容器进程退出码；超时或不可用时为空。")
    stdout: str = Field(default="", description="经过大小限制后的标准输出。")
    stderr: str = Field(default="", description="经过大小限制后的标准错误。")
    duration_ms: int = Field(ge=0, description="Docker 命令墙钟耗时。")
    output_truncated: bool = Field(default=False, description="stdout/stderr 是否因大小限制被截断。")
    error: str | None = Field(default=None, description="失败、超时或不可用摘要。")
    artifacts: list[ArtifactRecord] = Field(default_factory=list, description="执行后 Workspace 中登记的文件。")


class SandboxRuntimeStatus(BaseModel):
    """Swagger 和 Agent Console 使用的 Sandbox Backend 状态。"""

    backend: Literal["docker"] = Field(description="当前隔离后端。")
    available: bool = Field(description="Docker Engine 是否可连接。")
    docker_version: str | None = Field(default=None, description="可用时返回 Docker Server Version。")
    workspace_root: str = Field(description="受控 Workspace 根目录。")
    profile: SandboxProfile = Field(description="当前固定隔离与资源限制。")
    error: str | None = Field(default=None, description="Docker 不可用时的错误摘要。")
