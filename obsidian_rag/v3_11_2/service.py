from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from obsidian_rag.config import RagConfig, resolve_ingest_path
from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.docling_ingestion import DoclingIngestion
from obsidian_rag.pipeline import make_embedding_client
from obsidian_rag.v3_11_2.frameworks import (
    FrameworkRun,
    run_langchain_parent,
    run_llamaindex_hierarchical,
    run_llamaindex_semantic,
)
from obsidian_rag.v3_11_2.schemas import (
    FrameworkChunkView,
    FrameworkCompareRequest,
    FrameworkCompareResponse,
    FrameworkHitView,
    FrameworkRuntimeResponse,
    FrameworkStrategyResult,
    FrameworkTraceEvent,
)


class FrameworkComparisonService:
    """V3.11.2 比较编排；框架算法全部委托给 LangChain/LlamaIndex 官方组件。"""

    def __init__(
        self,
        config: RagConfig,
        docling: DoclingIngestion | None = None,
        embedding_client=None,
    ):
        self.config = config
        self._docling = docling
        self._embedding_client = embedding_client

    def compare(self, request: FrameworkCompareRequest) -> FrameworkCompareResponse:
        path = self._resolve_path(request.path)
        if not path.is_file():
            raise ValueError("V3.11.2 compare 只接受单个文件，以控制重复建索引成本。")
        conversion = self.docling.convert_file(path)
        debug_breakpoint(
            "v3_11_2.compare.after_docling",
            source=conversion.source,
            markdown_chars=len(conversion.markdown),
        )
        metadata = {"source": conversion.source, "title": conversion.title}
        embedding = self.embedding_client

        langchain = run_langchain_parent(
            conversion.markdown,
            metadata,
            request.query,
            embedding,
            request.langchain_parent_chars,
            request.langchain_child_chars,
            request.langchain_overlap_chars,
            request.top_k,
        )
        debug_breakpoint("v3_11_2.compare.after_langchain", strategy=langchain.strategy, chunks=langchain.chunk_count)
        hierarchical = run_llamaindex_hierarchical(
            conversion.markdown,
            metadata,
            request.query,
            embedding,
            request.llama_parent_tokens,
            request.llama_child_tokens,
            request.llama_overlap_tokens,
            request.top_k,
        )
        debug_breakpoint(
            "v3_11_2.compare.after_llama_hierarchical",
            strategy=hierarchical.strategy,
            chunks=hierarchical.chunk_count,
        )
        semantic = run_llamaindex_semantic(
            conversion.markdown,
            metadata,
            request.query,
            embedding,
            request.semantic_breakpoint_percentile,
            request.top_k,
        )
        debug_breakpoint(
            "v3_11_2.compare.after_llama_semantic",
            strategy=semantic.strategy,
            chunks=semantic.chunk_count,
        )
        runs = [langchain, hierarchical, semantic]
        return FrameworkCompareResponse(
            source=conversion.source,
            title=conversion.title,
            query=request.query,
            embedding_provider=self.config.embedding_provider,
            results=[_strategy_result(run, request.max_preview_chunks) for run in runs],
            trace=[
                FrameworkTraceEvent(
                    stage="docling",
                    detail="DocumentConverter 导出共同 Markdown 输入。",
                    metadata={"chars": len(conversion.markdown)},
                ),
                *[
                    FrameworkTraceEvent(
                        stage=run.strategy,
                        detail="框架完成 request-scoped 内存切片、建索引和检索。",
                        metadata={"framework": run.framework, "chunks": run.chunk_count, "build_ms": run.build_ms},
                    )
                    for run in runs
                ],
            ],
        )

    def runtime(self) -> FrameworkRuntimeResponse:
        return FrameworkRuntimeResponse(
            version="v3.11.2",
            packages={
                "docling": _package_version("docling"),
                "langchain": _package_version("langchain"),
                "langchain-classic": _package_version("langchain-classic"),
                "llama-index-core": _package_version("llama-index-core"),
            },
            strategies=["recursive_parent", "hierarchical_auto_merge", "semantic_splitter"],
            persistence="request-scoped in-memory",
            shared_qdrant_mutation=False,
        )

    @property
    def docling(self) -> DoclingIngestion:
        if self._docling is None:
            self._docling = DoclingIngestion(
                tokenizer_model=self.config.docling_tokenizer_model,
                max_tokens=self.config.chunk_token_size,
            )
        return self._docling

    @property
    def embedding_client(self):
        if self._embedding_client is None:
            self._embedding_client = make_embedding_client(self.config)
        return self._embedding_client

    def _resolve_path(self, value: str | None) -> Path:
        return resolve_ingest_path(Path(value).expanduser() if value else None, self.config)


def _strategy_result(run: FrameworkRun, max_preview: int) -> FrameworkStrategyResult:
    return FrameworkStrategyResult(
        framework=run.framework,
        strategy=run.strategy,
        build_ms=run.build_ms,
        chunk_count=run.chunk_count,
        average_chars=run.average_chars,
        max_chars=run.max_chars,
        chunks=[
            FrameworkChunkView(node_id=item.node_id, text=item.text, metadata=item.metadata)
            for item in run.chunks[:max_preview]
        ],
        hits=[
            FrameworkHitView(
                node_id=item.node_id,
                text=item.text,
                score=item.score,
                hit_kind=item.hit_kind,
                metadata=item.metadata,
            )
            for item in run.hits
        ],
    )


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"
