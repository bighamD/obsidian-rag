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
        """探测 Docker Engine 是否可用；不可用时返回 available=False，绝不降级到宿主机。"""

        try:
            # 用 docker version 做轻量探活，5 秒超时避免卡住请求。
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
        """在短生命周期强隔离容器中执行一个白名单命令，返回结构化结果（不抛异常）。"""

        # 第一道闸：只允许 allowlist 里的程序名，校验的是程序名而非 shell 字符串。
        if request.command not in self.profile.allowed_commands:
            return _failed(request, workspace, f"命令不在 Sandbox allowlist：{request.command}")
        status = self.status()
        if not status.available:
            return _failed(request, workspace, status.error or "Docker Engine 不可用。", status="unavailable")

        # 唯一容器名，超时时可据此强制清理。
        container_name = f"rag-sandbox-{uuid4().hex[:12]}"
        # 组装强隔离参数：断网 + 资源上限 + 禁提权 + 丢弃所有 capability。
        command = [
            "docker", "run", "--rm", "--name", container_name,
            "--network", "none" if self.profile.network_disabled else "bridge",
            "--memory", f"{self.profile.memory_mb}m",
            "--cpus", str(self.profile.cpus),
            "--pids-limit", str(self.profile.pids_limit),
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
        ]
        # 根文件系统只读，仅 /tmp 可写且禁执行，进一步收窄可写面。
        if self.profile.read_only_root:
            command.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
        # 只挂载当前 Run 的 Workspace；command/args 作为独立数组元素，不经过 shell 解析。
        command.extend([
            "-v", f"{workspace.host_path}:{workspace.container_path}:rw",
            "-w", workspace.container_path,
            self.profile.image,
            request.command,
            *request.args,
        ])
        started = perf_counter()
        try:
            # 阻塞等待容器内进程结束；容器主进程退出即容器停止，--rm 自动删除。
            # text=False 按 bytes 收集，避免非法编码在此处抛错。
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
            # 超时时容器可能仍在运行，用唯一容器名强制删除，防止残留。
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
    """按上限截断 stdout/stderr 并安全解码，防止超大输出撑爆内存或响应。"""

    combined = len(stdout) + len(stderr)
    truncated = combined > limit
    if truncated:
        # 超限时 stdout 最多占一半，剩余额度留给 stderr。
        stdout_limit = min(len(stdout), limit // 2)
        stderr_limit = max(0, limit - stdout_limit)
        stdout = stdout[:stdout_limit]
        stderr = stderr[:stderr_limit]
    # errors="replace"：非法字节替换为占位符而非抛异常。
    return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), truncated


def _failed(request, workspace, error, *, duration_ms=0, status="failed") -> SandboxExecutionResult:
    """统一构造失败结果，让 allowlist 拒绝/Docker 不可用/OSError 都返回而非抛异常。"""

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
