from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from obsidian_rag.v3_12.client.manager import McpClientManager, McpServerDefinition
from obsidian_rag.v3_12.service import McpIntegrationService


def get_workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_mcp_manager() -> McpClientManager:
    workspace_root = get_workspace_root()
    timeout_seconds = float(os.getenv("RAG_MCP_TIMEOUT_SECONDS", "15"))
    python = sys.executable
    return McpClientManager(
        [
            McpServerDefinition(
                name="demo",
                description="低风险测试工具：食品温度查询和时区时间。",
                command=python,
                args=("-m", "obsidian_rag.v3_12.servers.demo_server"),
                cwd=workspace_root,
                timeout_seconds=timeout_seconds,
            ),
            McpServerDefinition(
                name="rag",
                description="把本地 Obsidian RAG 检索和 Collection 列表暴露为 MCP Tools。",
                command=python,
                args=("-m", "obsidian_rag.v3_12.servers.rag_server"),
                cwd=workspace_root,
                timeout_seconds=timeout_seconds,
            ),
        ]
    )


@lru_cache(maxsize=1)
def get_mcp_service() -> McpIntegrationService:
    max_result_bytes = int(os.getenv("RAG_MCP_MAX_RESULT_BYTES", "262144"))
    return McpIntegrationService(get_mcp_manager(), max_result_bytes=max_result_bytes)
