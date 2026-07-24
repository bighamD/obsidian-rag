from __future__ import annotations

from typing import Any

from mcp.types import CallToolResult, Tool

from obsidian_rag.v3_12.schemas import McpContentBlock, McpToolDefinition


def adapt_tool(server_name: str, tool: Tool) -> McpToolDefinition:
    """把 MCP Tool Schema 转成项目稳定的工具描述。"""

    annotations = tool.annotations
    return McpToolDefinition(
        server_name=server_name,
        name=tool.name,
        namespaced_name=f"{server_name}::{tool.name}",
        title=tool.title,
        description=tool.description,
        input_schema=dict(tool.inputSchema),
        output_schema=dict(tool.outputSchema) if tool.outputSchema else None,
        read_only=annotations.readOnlyHint if annotations else None,
    )


def adapt_content(result: CallToolResult) -> list[McpContentBlock]:
    """保留 MCP Content Block 类型，同时投影成 Swagger 可展示 JSON。"""

    blocks: list[McpContentBlock] = []
    for block in result.content:
        payload = block.model_dump(mode="json", by_alias=True, exclude_none=True)
        blocks.append(McpContentBlock(type=str(payload.get("type", "unknown")), payload=payload))
    return blocks


def structured_content(result: CallToolResult) -> dict[str, Any] | None:
    value = result.structuredContent
    return dict(value) if value is not None else None
