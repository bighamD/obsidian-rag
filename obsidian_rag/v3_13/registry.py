from __future__ import annotations

from obsidian_rag.core.schemas import PlannerToolDefinition
from obsidian_rag.core.tools import ToolDefinition, ToolResult
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_12_3.registry import build_agent_tool_registry


def build_permission_agent_tool_registry(retrieval_service, manager: McpConnectionManager):
    """复用 Local/MCP Registry，并加入一个无副作用的 confirm 教学工具。"""

    registry, planner_tools, errors = build_agent_tool_registry(retrieval_service, manager)

    def simulate_workspace_write(path: str, content: str) -> ToolResult:
        return ToolResult(
            tool_name="local::simulate_workspace_write",
            status="success",
            data={"simulated": True, "path": path, "content_length": len(content)},
            metadata={"source": "local", "side_effect": False},
        )

    definition = ToolDefinition(
        name="local::simulate_workspace_write",
        description="教学用文件写入请求；Policy 应要求 confirm，本工具本身不会写入磁盘。",
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
        source="local",
        risk_level="confirm",
        required_permission="tool.write",
        scope="workspace",
    )
    registry.register(definition.name, simulate_workspace_write, definition)
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
