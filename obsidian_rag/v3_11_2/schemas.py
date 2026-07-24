from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class FrameworkCompareRequest(BaseModel):
    """同一 Docling 文档、query 和 embedding 下的三策略比较请求。"""

    path: str | None = Field(default=None, description="单个本地文档；为空时 RAG_VAULT_PATH 必须指向文件。")
    query: str = Field(min_length=1, description="三条框架检索路线共同使用的问题。")
    top_k: int = Field(default=4, ge=1, le=20, description="每条 strategy 的检索结果数量。")
    langchain_parent_chars: int = Field(default=2000, ge=200, le=20000, description="LangChain parent splitter 字符大小。")
    langchain_child_chars: int = Field(default=400, ge=50, le=5000, description="LangChain child splitter 字符大小。")
    langchain_overlap_chars: int = Field(default=50, ge=0, le=1000, description="LangChain recursive splitter 字符重叠。")
    llama_parent_tokens: int = Field(default=1024, ge=128, le=8000, description="LlamaIndex 顶层 node token 大小。")
    llama_child_tokens: int = Field(default=256, ge=32, le=4000, description="LlamaIndex leaf node token 大小。")
    llama_overlap_tokens: int = Field(default=20, ge=0, le=500, description="LlamaIndex SentenceSplitter token overlap。")
    semantic_breakpoint_percentile: int = Field(
        default=95,
        ge=50,
        le=99,
        description="SemanticSplitter 相邻句组差异分位数阈值；越低通常产生越多 nodes。",
    )
    max_preview_chunks: int = Field(default=20, ge=1, le=100, description="每条 strategy 最多返回多少个 chunk/node 预览。")

    @model_validator(mode="after")
    def validate_sizes(self) -> "FrameworkCompareRequest":
        if self.langchain_parent_chars <= self.langchain_child_chars:
            raise ValueError("langchain_parent_chars must be larger than langchain_child_chars")
        if self.llama_parent_tokens <= self.llama_child_tokens:
            raise ValueError("llama_parent_tokens must be larger than llama_child_tokens")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "knowledge/manual.pdf",
                    "query": "部署失败时应该如何回滚？",
                    "top_k": 4,
                    "langchain_parent_chars": 2000,
                    "langchain_child_chars": 400,
                    "llama_parent_tokens": 1024,
                    "llama_child_tokens": 256,
                    "semantic_breakpoint_percentile": 95,
                }
            ]
        }
    }


class FrameworkChunkView(BaseModel):
    """框架切片器产生的 child/node 预览。"""

    node_id: str = Field(description="LangChain/LlamaIndex 节点标识。")
    text: str = Field(description="框架产生的 chunk/node 文本。")
    metadata: dict[str, Any] = Field(description="框架 metadata 调试投影。")


class FrameworkHitView(BaseModel):
    """检索命中或父级合并后的可观察结果。"""

    node_id: str = Field(description="框架节点或 parent document ID。")
    text: str = Field(description="命中 child 或最终返回 context。")
    score: float | None = Field(description="框架检索分数；ParentDocumentRetriever 返回 parent 时可能为 null。")
    hit_kind: str = Field(description="matched_child、returned_parent、matched_leaf、auto_merged_context 或 semantic_node。")
    metadata: dict[str, Any] = Field(description="节点 metadata。")


class FrameworkStrategyResult(BaseModel):
    """单条框架 strategy 的统一统计与结果。"""

    framework: str = Field(description="langchain 或 llamaindex。")
    strategy: str = Field(description="recursive_parent、hierarchical_auto_merge 或 semantic_splitter。")
    build_ms: float = Field(description="转换后的 Markdown 建索引并完成检索的耗时毫秒数。")
    chunk_count: int = Field(description="实际产生的 child/leaf/semantic nodes 数量。")
    average_chars: float = Field(description="chunks 平均字符数。")
    max_chars: int = Field(description="最大 chunk 字符数。")
    chunks: list[FrameworkChunkView] = Field(description="截断后的 chunk/node 预览。")
    hits: list[FrameworkHitView] = Field(description="命中 child 和最终 context。")


class FrameworkTraceEvent(BaseModel):
    """框架 compare 的事实事件，不包含隐藏推理。"""

    stage: str = Field(description="docling、langchain、llamaindex_hierarchical 或 llamaindex_semantic。")
    detail: str = Field(description="阶段说明。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="耗时、数量和配置等事实字段。")


class FrameworkCompareResponse(BaseModel):
    """三条 chunk/retrieval strategy 的横向比较。"""

    source: str = Field(description="Docling 转换的源文件。")
    title: str = Field(description="DoclingDocument 标题。")
    query: str = Field(description="共同检索问题。")
    embedding_provider: str = Field(description="共同使用的 embedding provider。")
    results: list[FrameworkStrategyResult] = Field(description="三条 strategy 的统一结果。")
    trace: list[FrameworkTraceEvent] = Field(description="Docling 和三框架阶段事实事件。")


class FrameworkRuntimeResponse(BaseModel):
    """V3.11.2 框架版本和实验边界。"""

    version: str = Field(description="学习版本号。")
    packages: dict[str, str] = Field(description="运行环境中的 Docling/LangChain/LlamaIndex 版本或 missing。")
    strategies: list[str] = Field(description="本版实现的三条 strategy。")
    persistence: str = Field(description="实验索引生命周期；固定为 request-scoped in-memory。")
    shared_qdrant_mutation: bool = Field(description="compare 是否修改共享 Qdrant；固定为 false。")
