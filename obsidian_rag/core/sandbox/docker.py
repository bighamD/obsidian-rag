from __future__ import annotations

import subprocess
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from obsidian_rag.core.sandbox.schemas import (
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxProfile,
    SandboxRuntimeStatus,
    SandboxWorkspace,
)


class DockerSandboxBackend:
    """使用短生命周期 Docker Container 提供真实进程和文件系统隔离。"""

    def __init__(self, profile: SandboxProfile, workspace_root: Path):
        self.profile = profile
        self.workspace_root = workspace_root

    def status(self) -> SandboxRuntimeStatus:
        try:
            completed = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return SandboxRuntimeStatus(
                backend="docker",
                available=True,
                docker_version=completed.stdout.strip() or None,
                workspace_root=str(self.workspace_root),
                profile=self.profile,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return SandboxRuntimeStatus(
                backend="docker",
                available=False,
                workspace_root=str(self.workspace_root),
                profile=self.profile,
                error=str(exc),
            )

    def execute(self, request: SandboxExecutionRequest, workspace: SandboxWorkspace) -> SandboxExecutionResult:
        if request.command not in self.profile.allowed_commands:
            return _failed(request, workspace, f"命令不在 Sandbox allowlist：{request.command}")
        status = self.status()
        if not status.available:
            return _failed(request, workspace, status.error or "Docker Engine 不可用。", status="unavailable")

        container_name = f"rag-sandbox-{uuid4().hex[:12]}"
        command = [
            "docker", "run", "--rm", "--name", container_name,
            "--network", "none" if self.profile.network_disabled else "bridge",
            "--memory", f"{self.profile.memory_mb}m",
            "--cpus", str(self.profile.cpus),
            "--pids-limit", str(self.profile.pids_limit),
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
        ]
        if self.profile.read_only_root:
            command.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
        command.extend([
            "-v", f"{workspace.host_path}:{workspace.container_path}:rw",
            "-w", workspace.container_path,
            self.profile.image,
            request.command,
            *request.args,
        ])
        started = perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=False,
                timeout=self.profile.timeout_seconds,
            )
            stdout, stderr, truncated = _bounded_output(
                completed.stdout or b"",
                completed.stderr or b"",
                self.profile.max_output_bytes,
            )
            return SandboxExecutionResult(
                run_id=request.run_id,
                workspace=workspace,
                status="success" if completed.returncode == 0 else "failed",
                command=request.command,
                args=request.args,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=_elapsed(started),
                output_truncated=truncated,
                error=None if completed.returncode == 0 else f"容器命令退出码 {completed.returncode}。",
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=5)
            stdout, stderr, truncated = _bounded_output(exc.stdout or b"", exc.stderr or b"", self.profile.max_output_bytes)
            return SandboxExecutionResult(
                run_id=request.run_id,
                workspace=workspace,
                status="timeout",
                command=request.command,
                args=request.args,
                stdout=stdout,
                stderr=stderr,
                duration_ms=_elapsed(started),
                output_truncated=truncated,
                error=f"命令超过 {self.profile.timeout_seconds} 秒，容器已终止。",
            )
        except OSError as exc:
            return _failed(request, workspace, str(exc), duration_ms=_elapsed(started), status="unavailable")


def _bounded_output(stdout: bytes, stderr: bytes, limit: int) -> tuple[str, str, bool]:
    combined = len(stdout) + len(stderr)
    truncated = combined > limit
    if truncated:
        stdout_limit = min(len(stdout), limit // 2)
        stderr_limit = max(0, limit - stdout_limit)
        stdout = stdout[:stdout_limit]
        stderr = stderr[:stderr_limit]
    return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), truncated


def _failed(request, workspace, error, *, duration_ms=0, status="failed") -> SandboxExecutionResult:
    return SandboxExecutionResult(
        run_id=request.run_id,
        workspace=workspace,
        status=status,
        command=request.command,
        args=request.args,
        duration_ms=duration_ms,
        error=error,
    )


def _elapsed(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
