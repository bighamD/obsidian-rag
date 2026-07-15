from __future__ import annotations

from pathlib import Path

from obsidian_rag.config import RagConfig, resolve_ingest_path, with_collection
from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.docling_ingestion import DoclingConversion, DoclingIngestion
from obsidian_rag.pipeline import active_chunk_schema_version, build_ingestion_chunks, ingest_path
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_11_1.schemas import (
    DoclingChunkView,
    DoclingChunksResponse,
    DoclingConversionSummary,
    DoclingConvertResponse,
    DoclingIngestRequest,
    DoclingIngestResponse,
    DoclingPathRequest,
    DoclingRuntimeResponse,
    DoclingSearchHit,
    DoclingSearchRequest,
    DoclingSearchResponse,
)


class DoclingLearningService:
    """V3.11.1 编排层；Docling 解析后执行共享 adaptive parent-child 摄取与检索。"""

    def __init__(self, config: RagConfig, adapter: DoclingIngestion | None = None):
        self.config = config
        self._adapter = adapter

    @property
    def adapter(self) -> DoclingIngestion:
        if self._adapter is None:
            self._adapter = DoclingIngestion(
                tokenizer_model=self.config.docling_tokenizer_model,
                max_tokens=self.config.chunk_token_size,
            )
        return self._adapter

    def convert(self, request: DoclingPathRequest) -> DoclingConvertResponse:
        path = self._resolve_path(request.path)
        if not path.is_file():
            raise ValueError("convert 只接受单个文件；目录请使用 chunks 或 ingest。")
        conversion = self.adapter.convert_file(path)
        debug_breakpoint("v3_11_1.convert.after_docling", source=conversion.source, status=conversion.status)
        return DoclingConvertResponse(document=_summary(conversion))

    def chunks(self, request: DoclingPathRequest) -> DoclingChunksResponse:
        path = self._resolve_path(request.path)
        batch = self.adapter.convert_and_chunk_path(path)
        chunks = build_ingestion_chunks(batch, self.config, self.adapter)
        debug_breakpoint(
            "v3_11_1.chunks.after_docling",
            document_count=len(batch.conversions),
            chunk_count=len(chunks),
            chunk_strategy=self.config.chunk_strategy,
            errors=batch.errors,
        )
        return DoclingChunksResponse(
            documents=[_summary(item) for item in batch.conversions],
            chunks=[_chunk_view(chunk) for chunk in chunks],
            errors=batch.errors,
            tokenizer_model=self.config.docling_tokenizer_model,
            max_tokens=self.config.chunk_token_size,
            chunk_strategy=self.config.chunk_strategy,
            parent_tokens=self.config.parent_chunk_tokens,
            child_tokens=self.config.child_chunk_tokens,
        )

    def ingest(self, request: DoclingIngestRequest) -> DoclingIngestResponse:
        request_config = with_collection(self.config, request.collection)
        path = resolve_ingest_path(Path(request.path).expanduser() if request.path else None, request_config)
        document_count, chunk_count = ingest_path(path, request_config, recreate=request.recreate)
        return DoclingIngestResponse(
            document_count=document_count,
            chunk_count=chunk_count,
            parser="docling",
            chunk_schema_version=active_chunk_schema_version(request_config),
            recreated=request.recreate,
            collection=request_config.collection_name,
        )

    def search(self, request: DoclingSearchRequest) -> DoclingSearchResponse:
        retrieval_service = RetrievalService(self.config)
        collection = retrieval_service.collection_name(request.collection)
        results = retrieval_service.search(
            request.query,
            top_k=request.top_k,
            mode=request.mode,
            collection=request.collection,
        )
        hits = []
        for result in results:
            metadata = result.chunk.metadata
            hits.append(
                DoclingSearchHit(
                    source=str(metadata.get("source", "unknown")),
                    score=float(result.score),
                    node_id=_optional_str(metadata.get("node_id")),
                    parent_id=_optional_str(metadata.get("parent_id")),
                    chunk_id=_optional_str(metadata.get("chunk_id")),
                    heading_path=[str(item) for item in metadata.get("heading_path", [])],
                    page_numbers=[int(item) for item in metadata.get("page_numbers", [])],
                    contextualized_text=result.chunk.text,
                    matched_child_text=str(metadata.get("matched_child_text") or result.chunk.text),
                    returned_parent_text=str(metadata.get("returned_parent_text") or result.chunk.text),
                    raw_text=str(metadata.get("raw_chunk_text") or result.chunk.text),
                    metadata=metadata,
                )
            )
        return DoclingSearchResponse(query=request.query, mode=request.mode, collection=collection, results=hits)

    def runtime(self) -> DoclingRuntimeResponse:
        return DoclingRuntimeResponse(
            version="v3.11.1",
            parser="docling",
            converter="Docling DocumentConverter",
            chunker="Docling blocks + LangChain RecursiveCharacterTextSplitter",
            chunk_strategy=self.config.chunk_strategy,
            tokenizer_model=self.config.docling_tokenizer_model,
            max_tokens=self.config.chunk_token_size,
            parent_tokens=self.config.parent_chunk_tokens,
            child_tokens=self.config.child_chunk_tokens,
            chunk_schema_version=active_chunk_schema_version(self.config),
            semantic_chunking=False,
        )

    def _resolve_path(self, value: str | None) -> Path:
        return resolve_ingest_path(Path(value).expanduser() if value else None, self.config)


def _summary(conversion: DoclingConversion) -> DoclingConversionSummary:
    preview = conversion.markdown if len(conversion.markdown) <= 4000 else f"{conversion.markdown[:4000]}..."
    return DoclingConversionSummary(
        source=conversion.source,
        title=conversion.title,
        status=conversion.status,
        page_count=conversion.page_count,
        item_count=conversion.item_count,
        markdown_preview=preview,
    )


def _chunk_view(chunk) -> DoclingChunkView:
    metadata = chunk.metadata
    return DoclingChunkView(
        node_id=str(metadata.get("node_id", "")),
        parent_id=_optional_str(metadata.get("parent_id")),
        child_index=int(metadata["child_index"]) if metadata.get("child_index") is not None else None,
        source=str(metadata.get("source", "unknown")),
        chunk_id=_optional_str(metadata.get("chunk_id")),
        heading_path=[str(item) for item in metadata.get("heading_path", [])],
        page_numbers=[int(item) for item in metadata.get("page_numbers", [])],
        raw_text=str(metadata.get("raw_chunk_text") or ""),
        contextualized_text=chunk.text,
        parent_text=str(metadata.get("parent_text") or chunk.text),
        metadata=metadata,
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
