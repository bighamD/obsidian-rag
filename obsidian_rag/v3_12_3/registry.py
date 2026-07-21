from __future__ import annotations

import json

from obsidian_rag.core.schemas import PlannerToolDefinition
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult, build_search_tool_registry
from obsidian_rag.v3_12_3.connection import McpConnectionManager


def build_agent_tool_registry(
    retrieval_service,
    manager: McpConnectionManager,
) -> tuple[ToolRegistry, list[PlannerToolDefinition], dict[str, str]]:
    """构建当前 Agent Run 使用的本地 + MCP Registry 与精简 Planner Catalog。"""

    registry = build_search_tool_registry(retrieval_service)
    remote_tools, errors = manager.list_tools()
    planner_tools: list[PlannerToolDefinition] = []
    schema_chars = 0

    for tool in remote_tools:
        def call_mcp(_name=tool.namespaced_name, **arguments) -> ToolResult:
            response = manager.call_tool(_name, arguments)
            prompt_data = response.structured_content
            if prompt_data is None:
                prompt_data = [block.payload for block in response.content]
            return ToolResult(
                tool_name=response.namespaced_name,
                status=response.status,
                error=response.error,
                metadata={
                    "source": "mcp",
                    "server_name": response.server_name,
                    "duration_ms": response.duration_ms,
                    "trace": [event.model_dump(mode="json") for event in response.trace],
                },
                data=prompt_data,
            )

        registry.register(
            tool.namespaced_name,
            call_mcp,
            ToolDefinition(
                name=tool.namespaced_name,
                description=tool.description or tool.title or tool.name,
                input_schema=tool.input_schema,
                read_only=tool.read_only,
                source="mcp",
                risk_level="safe" if tool.read_only is True else "confirm" if tool.read_only is False else "restricted",
                required_permission="tool.read" if tool.read_only is True else "tool.execute",
                scope="external_tool",
            ),
        )
        serialized_schema = json.dumps(tool.input_schema, ensure_ascii=False)
        if (
            len(planner_tools) < manager.registry.max_planner_tools
            and schema_chars + len(serialized_schema) <= manager.registry.max_tool_schema_chars
        ):
            planner_tools.append(
                PlannerToolDefinition(
                    name=tool.namespaced_name,
                    description=tool.description or tool.title or tool.name,
                    input_schema=tool.input_schema,
                    source="mcp",
                    read_only=tool.read_only,
                )
            )
            schema_chars += len(serialized_schema)

    return registry, planner_tools, errors
