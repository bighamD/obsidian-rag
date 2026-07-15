from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class FrameworkChunk:
    node_id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class FrameworkHit:
    node_id: str
    text: str
    score: float | None
    metadata: dict[str, Any]
    hit_kind: str


@dataclass(frozen=True)
class FrameworkRun:
    framework: str
    strategy: str
    build_ms: float
    chunk_count: int
    average_chars: float
    max_chars: int
    chunks: list[FrameworkChunk]
    hits: list[FrameworkHit]


def run_langchain_parent(
    text: str,
    metadata: dict[str, Any],
    query: str,
    embedding_client: Any,
    parent_size: int,
    child_size: int,
    overlap: int,
    top_k: int,
) -> FrameworkRun:
    try:
        from langchain_classic.retrievers import ParentDocumentRetriever
        from langchain_classic.storage import InMemoryStore
        from langchain_core.documents import Document
        from langchain_core.embeddings import Embeddings
        from langchain_core.vectorstores import InMemoryVectorStore
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise _missing_framework("LangChain", exc) from exc

    class EmbeddingAdapter(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return embedding_client.embed_texts(texts)

        def embed_query(self, value: str) -> list[float]:
            return embedding_client.embed_query(value)

    started = perf_counter()
    separators = ["\n# ", "\n## ", "\n\n", "\n", "。", "！", "？", ". ", " ", ""]
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_size,
        chunk_overlap=overlap,
        separators=separators,
        add_start_index=True,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size,
        chunk_overlap=min(overlap, max(0, child_size - 1)),
        separators=separators,
        add_start_index=True,
    )
    source_documents = [Document(page_content=text, metadata=metadata)]
    parent_documents = parent_splitter.split_documents(source_documents)
    child_documents = [child for parent in parent_documents for child in child_splitter.split_documents([parent])]
    vectorstore = InMemoryVectorStore(embedding=EmbeddingAdapter())
    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=InMemoryStore(),
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
        search_kwargs={"k": top_k},
    )
    retriever.add_documents(source_documents)
    child_hits = vectorstore.similarity_search_with_score(query, k=top_k)
    parent_hits = retriever.invoke(query)
    build_ms = (perf_counter() - started) * 1000

    chunks = [
        FrameworkChunk(
            node_id=f"langchain-child-{index}",
            text=document.page_content,
            metadata=dict(document.metadata),
        )
        for index, document in enumerate(child_documents)
    ]
    hits = [
        FrameworkHit(
            node_id=str(document.metadata.get("doc_id") or f"langchain-child-hit-{index}"),
            text=document.page_content,
            score=float(score),
            metadata=dict(document.metadata),
            hit_kind="matched_child",
        )
        for index, (document, score) in enumerate(child_hits)
    ]
    hits.extend(
        FrameworkHit(
            node_id=str(document.metadata.get("doc_id") or f"langchain-parent-{index}"),
            text=document.page_content,
            score=None,
            metadata=dict(document.metadata),
            hit_kind="returned_parent",
        )
        for index, document in enumerate(parent_hits)
    )
    return _run("langchain", "recursive_parent", build_ms, chunks, hits)


def run_llamaindex_hierarchical(
    text: str,
    metadata: dict[str, Any],
    query: str,
    embedding_client: Any,
    parent_size: int,
    child_size: int,
    overlap: int,
    top_k: int,
) -> FrameworkRun:
    try:
        from llama_index.core import Document, StorageContext, VectorStoreIndex
        from llama_index.core.node_parser import HierarchicalNodeParser
        from llama_index.core.node_parser.relational.hierarchical import get_leaf_nodes
        from llama_index.core.retrievers import AutoMergingRetriever
        from llama_index.core.schema import MetadataMode
    except ImportError as exc:
        raise _missing_framework("LlamaIndex", exc) from exc

    started = perf_counter()
    embed_model = _llama_embedding(embedding_client)
    documents = [Document(text=text, metadata=metadata)]
    parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[parent_size, child_size],
        chunk_overlap=overlap,
    )
    nodes = parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(nodes)
    index = VectorStoreIndex(leaf_nodes, storage_context=storage_context, embed_model=embed_model)
    base_retriever = index.as_retriever(similarity_top_k=top_k)
    leaf_hits = base_retriever.retrieve(query)
    merged_hits = AutoMergingRetriever(base_retriever, storage_context, verbose=False).retrieve(query)
    build_ms = (perf_counter() - started) * 1000

    chunks = [
        FrameworkChunk(
            node_id=node.node_id,
            text=node.get_content(metadata_mode=MetadataMode.NONE),
            metadata=dict(node.metadata),
        )
        for node in leaf_nodes
    ]
    hits = [_llama_hit(item, "matched_leaf") for item in leaf_hits]
    hits.extend(_llama_hit(item, "auto_merged_context") for item in merged_hits)
    return _run("llamaindex", "hierarchical_auto_merge", build_ms, chunks, hits)


def run_llamaindex_semantic(
    text: str,
    metadata: dict[str, Any],
    query: str,
    embedding_client: Any,
    breakpoint_percentile: int,
    top_k: int,
) -> FrameworkRun:
    try:
        from llama_index.core import Document, VectorStoreIndex
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.core.schema import MetadataMode
    except ImportError as exc:
        raise _missing_framework("LlamaIndex", exc) from exc

    started = perf_counter()
    embed_model = _llama_embedding(embedding_client)
    parser = SemanticSplitterNodeParser.from_defaults(
        embed_model=embed_model,
        buffer_size=1,
        breakpoint_percentile_threshold=breakpoint_percentile,
    )
    nodes = parser.get_nodes_from_documents([Document(text=text, metadata=metadata)])
    index = VectorStoreIndex(nodes, embed_model=embed_model)
    hits_raw = index.as_retriever(similarity_top_k=top_k).retrieve(query)
    build_ms = (perf_counter() - started) * 1000
    chunks = [
        FrameworkChunk(
            node_id=node.node_id,
            text=node.get_content(metadata_mode=MetadataMode.NONE),
            metadata=dict(node.metadata),
        )
        for node in nodes
    ]
    hits = [_llama_hit(item, "semantic_node") for item in hits_raw]
    return _run("llamaindex", "semantic_splitter", build_ms, chunks, hits)


def _llama_embedding(embedding_client: Any):
    try:
        from llama_index.core.base.embeddings.base import BaseEmbedding
        from pydantic import PrivateAttr
    except ImportError as exc:
        raise _missing_framework("LlamaIndex", exc) from exc

    class EmbeddingAdapter(BaseEmbedding):
        _client: Any = PrivateAttr()

        def __init__(self):
            super().__init__(model_name=type(embedding_client).__name__)
            self._client = embedding_client

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._client.embed_query(query)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._client.embed_query(query)

        def _get_text_embedding(self, value: str) -> list[float]:
            return self._client.embed_texts([value])[0]

        def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            return self._client.embed_texts(texts)

    return EmbeddingAdapter()


def _llama_hit(item: Any, hit_kind: str) -> FrameworkHit:
    try:
        from llama_index.core.schema import MetadataMode
    except ImportError as exc:
        raise _missing_framework("LlamaIndex", exc) from exc
    return FrameworkHit(
        node_id=item.node.node_id,
        text=item.node.get_content(metadata_mode=MetadataMode.NONE),
        score=float(item.get_score()) if item.get_score() is not None else None,
        metadata=dict(item.node.metadata),
        hit_kind=hit_kind,
    )


def _run(
    framework: str,
    strategy: str,
    build_ms: float,
    chunks: list[FrameworkChunk],
    hits: list[FrameworkHit],
) -> FrameworkRun:
    lengths = [len(chunk.text) for chunk in chunks]
    return FrameworkRun(
        framework=framework,
        strategy=strategy,
        build_ms=round(build_ms, 3),
        chunk_count=len(chunks),
        average_chars=round(sum(lengths) / len(lengths), 2) if lengths else 0.0,
        max_chars=max(lengths, default=0),
        chunks=chunks,
        hits=hits,
    )


def _missing_framework(name: str, exc: ImportError) -> RuntimeError:
    return RuntimeError(f"{name} 依赖未安装，请执行 `pip install -e .` 后重试：{exc}")
