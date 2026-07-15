from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.config import COLLECTION_NAME_PATTERN

SearchMode = Literal["dense", "keyword", "hybrid"]


class DoclingPathRequest(BaseModel):
    """Docling convert/chunks 的本地文件或目录输入。"""

    path: str | None = Field(default=None, description="本地文件或目录的绝对路径；为空时使用 RAG_VAULT_PATH。")

    model_config = {"json_schema_extra": {"examples": [{"path": "/absolute/path/to/manual.pdf"}]}}


class DoclingConversionSummary(BaseModel):
    """DoclingDocument 的轻量摘要，不返回完整框架对象。"""

    source: str = Field(description="源文件相对路径或绝对路径。")
    title: str = Field(description="DoclingDocument 标题。")
    status: str = Field(description="Docling ConversionResult 状态。")
    page_count: int = Field(description="Docling 识别的页数；无页概念的格式可能为 0。")
    item_count: int = Field(description="DoclingDocument 结构项数量。")
    markdown_preview: str = Field(description="DoclingDocument 导出的 Markdown 截断预览。")


class DoclingConvertResponse(BaseModel):
    """单文件 Docling 转换结果。"""

    document: DoclingConversionSummary = Field(description="转换后的统一文档摘要。")
    framework: str = Field(default="docling", description="本次使用的文档解析框架。")


class DoclingChunkView(BaseModel):
    """Docling HybridChunker 原始 chunk 与 embedding 文本投影。"""

    node_id: str = Field(description="映射到 Qdrant point 的稳定节点 ID。")
    source: str = Field(description="源文件路径。")
    chunk_id: str | None = Field(default=None, description="文档 YAML 或编号标题提供的业务引用 ID，例如 KB-072、VU-001。")
    heading_path: list[str] = Field(description="Docling meta 中的标题路径。")
    page_numbers: list[int] = Field(description="Docling provenance 中涉及的页码。")
    raw_text: str = Field(description="HybridChunker 产生的原始 chunk.text。")
    contextualized_text: str = Field(description="HybridChunker.contextualize() 生成、实际用于 embedding 的文本。")
    metadata: dict[str, Any] = Field(description="写入 Qdrant payload 的完整 metadata 调试投影。")


class DoclingChunksResponse(BaseModel):
    """只读转换与 HybridChunker 预览；不会写入索引。"""

    documents: list[DoclingConversionSummary] = Field(description="成功转换的 DoclingDocument 摘要。")
    chunks: list[DoclingChunkView] = Field(description="生成的全部 Docling chunks。")
    errors: list[str] = Field(description="目录转换中跳过的失败文件和错误。")
    tokenizer_model: str = Field(description="HybridChunker 使用的 HuggingFace tokenizer。")
    max_tokens: int = Field(description="HybridChunker 的 token 上限。")


class DoclingIngestRequest(BaseModel):
    """通过共享 V0 Docling 摄取链路重建索引。"""

    path: str | None = Field(default=None, description="本地文件或目录的绝对路径；为空时使用 RAG_VAULT_PATH。")
    recreate: bool = Field(default=True, description="是否重建当前 Qdrant collection。首次运行应为 true。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="写入目标知识库 Collection；为空时使用 RAG_COLLECTION。",
    )

    model_config = {"json_schema_extra": {"examples": [{"collection": "food_safety", "recreate": True}]}}


class DoclingIngestResponse(BaseModel):
    """共享 Qdrant/keyword index 写入结果。"""

    document_count: int = Field(description="Docling 成功转换的文档数。")
    chunk_count: int = Field(description="写入索引的 HybridChunker chunk 数。")
    parser: str = Field(description="共享 pipeline 固定使用的文档解析框架，当前为 docling。")
    chunk_schema_version: str = Field(description="写入 metadata 的 chunk schema 版本。")
    recreated: bool = Field(description="是否重建了 Qdrant collection。")
    collection: str = Field(description="本次实际写入的知识库 Collection。")


class DoclingSearchRequest(BaseModel):
    """对共享 Docling 索引执行检索。"""

    query: str = Field(min_length=1, description="检索问题。")
    top_k: int = Field(default=5, ge=1, le=50, description="最多返回多少个 chunks。")
    mode: SearchMode = Field(default="hybrid", description="dense、keyword 或 hybrid。")
    collection: str | None = Field(
        default=None,
        pattern=COLLECTION_NAME_PATTERN,
        description="检索目标知识库 Collection；为空时使用 RAG_COLLECTION。",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "这个文档的核心结论是什么？", "top_k": 5, "mode": "hybrid", "collection": "food_safety"}
            ]
        }
    }


class DoclingSearchHit(BaseModel):
    """共享检索返回的 contextualized Docling chunk。"""

    source: str = Field(description="源文件路径。")
    score: float = Field(description="当前检索模式的排序分数。")
    node_id: str | None = Field(default=None, description="Docling chunk 映射后的节点 ID。")
    chunk_id: str | None = Field(default=None, description="知识库中可选的业务引用 ID，例如 KB-072、VU-001。")
    heading_path: list[str] = Field(description="标题路径。")
    page_numbers: list[int] = Field(description="页码定位。")
    contextualized_text: str = Field(description="检索命中的实际 embedding/context 文本。")
    raw_text: str = Field(description="HybridChunker 原始文本，仅用于对比调试。")
    metadata: dict[str, Any] = Field(description="完整 metadata。")


class DoclingSearchResponse(BaseModel):
    """V3.11.1 检索结果。"""

    query: str = Field(description="原始问题。")
    mode: SearchMode = Field(description="检索模式。")
    collection: str = Field(description="本次实际检索的知识库 Collection。")
    results: list[DoclingSearchHit] = Field(description="命中的 Docling chunks。")


class DoclingRuntimeResponse(BaseModel):
    """可安全公开的 V3.11.1 框架边界。"""

    version: str = Field(description="学习版本号。")
    parser: str = Field(description="共享 V0 固定使用的文档解析框架，当前为 docling。")
    converter: str = Field(description="文档转换组件。")
    chunker: str = Field(description="切片组件。")
    tokenizer_model: str = Field(description="HybridChunker tokenizer。")
    max_tokens: int = Field(description="HybridChunker token 上限。")
    chunk_schema_version: str = Field(description="Docling chunk schema 版本。")
    semantic_chunking: bool = Field(description="是否包含语义切片；V3.11.1 固定为 false。")
