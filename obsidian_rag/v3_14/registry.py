from __future__ import annotations

from obsidian_rag.core.collections import SearchCollectionPolicy
from obsidian_rag.core.schemas import PlannerToolDefinition
from obsidian_rag.core.sandbox import SandboxRuntime
from obsidian_rag.core.tools import ToolDefinition, ToolResult
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_13.registry import build_permission_agent_tool_registry


def build_sandbox_agent_tool_registry(
    retrieval_service,
    manager: McpConnectionManager,
    sandbox: SandboxRuntime,
    collection_policy: SearchCollectionPolicy | None = None,
    side_effect_risk_level: str = "safe",
):
    """在 V3.13 Registry 上增加受控 Sandbox 文件和命令工具。"""

    registry, planner_tools, errors = build_permission_agent_tool_registry(
        retrieval_service,
        manager,
        collection_policy,
    )

    def read_file(path: str, _run_id: str) -> ToolResult:
        return _call("sandbox::read_file", lambda: sandbox.read_file(_run_id, path))

    def write_file(path: str, content: str, _run_id: str) -> ToolResult:
        return _call("sandbox::write_file", lambda: sandbox.write_file(_run_id, path, content))

    def list_files(_run_id: str) -> ToolResult:
        return _call("sandbox::list_files", lambda: sandbox.list_files(_run_id))

    def run_command(command: str, args: list[str], _run_id: str) -> ToolResult:
        result = sandbox.run_command(_run_id, command, args)
        return ToolResult(
            tool_name="sandbox::run_command",
            status="success" if result.status == "success" else "failed",
            data=result.model_dump(mode="json"),
            error=result.error,
            metadata={
                "source": "sandbox",
                "duration_ms": result.duration_ms,
                "workspace_id": result.workspace.workspace_id,
                "artifact_count": len(result.artifacts),
                "output_truncated": result.output_truncated,
            },
        )

    definitions = [
        (
            ToolDefinition(
                name="sandbox::read_file",
                description="读取本次 Agent Run 隔离 Workspace 中的 UTF-8 文本文件。",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string", "minLength": 1}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                read_only=True,
                source="sandbox",
                risk_level="safe",
                required_permission="sandbox.read",
                scope="sandbox",
            ),
            read_file,
        ),
        (
            ToolDefinition(
                name="sandbox::write_file",
                description=(
                    "在本次 Agent Run 的隔离 Workspace 中创建或覆盖 UTF-8 文本文件并登记 Artifact。"
                    "当用户明确要求创建、编写、生成或保存脚本/文件时使用；path 应包含合理文件名，"
                    "content 必须是完整可用内容，不能使用省略号或占位符。"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "minLength": 1},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
                read_only=False,
                source="sandbox",
                risk_level=side_effect_risk_level,
                required_permission="sandbox.write",
                scope="sandbox",
            ),
            write_file,
        ),
        (
            ToolDefinition(
                name="sandbox::list_files",
                description="列出本次 Agent Run 隔离 Workspace 中登记的 Artifacts。",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                read_only=True,
                source="sandbox",
                risk_level="safe",
                required_permission="sandbox.read",
                scope="sandbox",
            ),
            list_files,
        ),
        (
            ToolDefinition(
                name="sandbox::run_command",
                description=(
                    "在无网络、限资源的 Docker Sandbox 中运行、测试或验证已创建的脚本。"
                    "仅执行白名单程序和参数数组；需要运行新脚本时，应依赖前面的 sandbox::write_file 步骤。"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "enum": sandbox.backend.profile.allowed_commands},
                        "args": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
                    },
                    "required": ["command", "args"],
                    "additionalProperties": False,
                },
                read_only=False,
                source="sandbox",
                risk_level=side_effect_risk_level,
                required_permission="sandbox.execute",
                scope="sandbox",
            ),
            run_command,
        ),
    ]
    for definition, handler in definitions:
        registry.register(definition.name, handler, definition)
        planner_tools.append(
            PlannerToolDefinition(
                name=definition.name,
                description=definition.description,
                input_schema=definition.input_schema,
                source=definition.source,
                read_only=definition.read_only,
            )
        )
    return registry, planner_tools, errors


def _call(name: str, handler) -> ToolResult:
    try:
        return ToolResult(tool_name=name, status="success", data=handler(), metadata={"source": "sandbox"})
    except Exception as exc:
        return ToolResult(
            tool_name=name,
            status="failed",
            error=str(exc),
            metadata={"source": "sandbox", "error_type": type(exc).__name__},
        )
