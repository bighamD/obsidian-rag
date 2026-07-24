from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from obsidian_rag.core.collections import KnowledgeBaseManifest
from obsidian_rag.core.tools import ToolRegistry
from obsidian_rag.v1.schemas import SearchHit, to_search_hit
from obsidian_rag.v3_16.schemas import DeepAgentAskRequest


class SearchNotesInput(BaseModel):
    """模型可见的 search_notes 参数，不暴露连接、Principal 或服务对象。"""

    query: str = Field(min_length=1, description="根据用户目标生成的知识库检索词。")
    top_k: int | None = Field(default=None, ge=1, le=10, description="最多返回多少条知识块；为空时使用请求默认值。")
    mode: Literal["dense", "keyword", "hybrid"] | None = Field(
        default=None,
        description="检索模式；为空时使用请求默认值。",
    )
    collection: str | None = Field(default=None, description="只检索一个明确的知识库 Collection。")
    collections: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="需要跨库检索时选择的 Collections，最多三个；不要与 collection 同时填写。",
    )


class SearchNotesToolAdapter:
    """把公共 ToolRegistry 的 search_notes 适配为 LangChain StructuredTool。"""

    def __init__(
        self,
        registry: ToolRegistry,
        request: DeepAgentAskRequest,
        knowledge_bases: list[KnowledgeBaseManifest],
    ):
        self.registry = registry
        self.request = request
        self.knowledge_bases = knowledge_bases

    def as_tool(self) -> BaseTool:
        return StructuredTool.from_function(
            func=self._invoke,
            name="search_notes",
            description=self.description(),
            args_schema=SearchNotesInput,
        )

    def description(self) -> str:
        catalog = "; ".join(
            f"{item.collection}: {item.description}"
            for item in self.knowledge_bases
            if item.enabled
        )
        return (
            "在本地知识库执行 dense、keyword 或 hybrid 检索。"
            "涉及菜谱、食品安全或项目文档事实时，必须先调用本工具并等待 ToolMessage，"
            "再生成答案或 write_file.content。可用知识库："
            f"{catalog or '仅默认 Collection'}"
        )

    def _invoke(
        self,
        query: str,
        top_k: int | None = None,
        mode: Literal["dense", "keyword", "hybrid"] | None = None,
        collection: str | None = None,
        collections: list[str] | None = None,
    ) -> str:
        selected_collection = self.request.collection or collection
        selected_collections = [] if selected_collection else list(collections or [])
        filters = self.request.filters
        result = self.registry.run(
            "search_notes",
            query=query,
            top_k=top_k or self.request.top_k,
            mode=mode or self.request.mode,
            filters=filters,
            collection=selected_collection,
            collections=selected_collections or None,
        )
        hits: list[SearchHit] = [to_search_hit(item) for item in result.results]
        selected_collections = [str(item) for item in result.metadata.get("selected_collections", [])]
        payload = {
            "tool": "search_notes",
            "status": result.status,
            "query": query,
            "mode": mode or self.request.mode,
            "result_count": len(hits),
            "selected_collections": selected_collections,
            "results": [_tool_hit_payload(item, selected_collections) for item in hits],
            "metadata": result.metadata,
            "error": result.error,
        }
        return json.dumps(payload, ensure_ascii=False)


def _tool_hit_payload(hit: SearchHit, selected_collections: list[str]) -> dict:
    """为 ToolMessage 补齐 DeepAgents 下一轮模型真正需要的显式事实字段。"""

    payload = hit.model_dump(mode="json")
    payload["content"] = hit.text or hit.text_preview
    payload["collection"] = str(hit.metadata.get("collection") or (selected_collections[0] if selected_collections else ""))
    return payload
