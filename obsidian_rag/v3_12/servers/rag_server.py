from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from obsidian_rag.config import load_config
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry


mcp = FastMCP(
    "obsidian-rag-v3.12-rag",
    instructions="把本地 Obsidian RAG 的只读检索能力暴露给其他 MCP Client。",
    log_level="ERROR",
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=True)
def search_notes(
    query: str,
    top_k: int = 5,
    mode: Literal["dense", "keyword", "hybrid"] = "hybrid",
    collection: str | None = None,
) -> dict[str, Any]:
    """在指定知识库 Collection 中检索相关知识块。"""

    if not query.strip():
        raise ValueError("query 不能为空")
    if not 1 <= top_k <= 20:
        raise ValueError("top_k 必须在 1 到 20 之间")
    service = RetrievalService(load_config())
    results = service.search(query, top_k=top_k, mode=mode, collection=collection)
    actual_collection = service.collection_name(collection)
    return {
        "query": query,
        "mode": mode,
        "collection": actual_collection,
        "results": [to_search_hit(result).model_dump(mode="json") for result in results],
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=True)
def list_collections() -> dict[str, Any]:
    """列出 knowledge_bases.yaml 中启用的知识库 Collection。"""

    registry_path = Path(os.getenv("RAG_KNOWLEDGE_BASE_REGISTRY", "knowledge_bases.yaml"))
    registry = KnowledgeBaseRegistry(registry_path)
    manifests = registry.load()
    return {
        "registry_path": str(registry.path),
        "collections": [
            manifest.model_dump(mode="json")
            for manifest in manifests
            if manifest.enabled
        ],
        "errors": registry.errors,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
