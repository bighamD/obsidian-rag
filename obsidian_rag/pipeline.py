from __future__ import annotations

from pathlib import Path

from obsidian_rag.adaptive_chunking import ADAPTIVE_CHUNK_SCHEMA_VERSION, adaptive_parent_child_chunks
from obsidian_rag.config import RagConfig, require_api_key
from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.docling_ingestion import DOCLING_CHUNK_SCHEMA_VERSION, DoclingBatch, DoclingIngestion
from obsidian_rag.embeddings import HashEmbeddingClient, OllamaEmbeddingClient, OpenAIEmbeddingClient
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.parent_retrieval import expand_parent_results
from obsidian_rag.prompting import build_rag_messages
from obsidian_rag.qdrant_store import QdrantVectorStore
from obsidian_rag.schema import SearchResult


def make_embedding_client(config: RagConfig):
    if config.embedding_provider == "hash":
        return HashEmbeddingClient(dimensions=config.embedding_dimensions)
    if config.embedding_provider == "ollama":
        return OllamaEmbeddingClient(
            base_url=config.ollama_base_url,
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
        )
    require_api_key(config)
    return OpenAIEmbeddingClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
    )


def make_store(config: RagConfig) -> QdrantVectorStore:
    if config.qdrant_url:
        return QdrantVectorStore(
            url=config.qdrant_url,
            collection_name=config.collection_name,
            embedding_dimensions=config.embedding_dimensions,
        )
    return QdrantVectorStore(
        path=config.db_path,
        collection_name=config.collection_name,
        embedding_dimensions=config.embedding_dimensions,
    )


def make_docling_ingestion(config: RagConfig) -> DoclingIngestion:
    return DoclingIngestion(
        tokenizer_model=config.docling_tokenizer_model,
        max_tokens=config.chunk_token_size,
    )


def ingest_path(path: Path, config: RagConfig, recreate: bool = False) -> tuple[int, int]:
    ingestion = make_docling_ingestion(config)
    batch = ingestion.convert_and_chunk_path(path)
    if batch.errors and not batch.conversions:
        raise RuntimeError("Docling failed to convert every document: " + "; ".join(batch.errors))
    document_count = len(batch.conversions)
    chunks = build_ingestion_chunks(batch, config, ingestion)
    debug_breakpoint(
        "ingest.after_load",
        path=path,
        document_parser="docling",
        document_count=document_count,
        errors=batch.errors,
    )
    if not chunks:
        raise RuntimeError("Ingest produced no chunks; existing indexes were not modified.")
    debug_breakpoint("ingest.after_chunks", chunk_count=len(chunks), first_chunk=chunks[0] if chunks else None)
    embeddings = make_embedding_client(config)
    vectors = embeddings.embed_texts([chunk.text for chunk in chunks])
    debug_breakpoint(
        "ingest.after_embeddings",
        vector_count=len(vectors),
        vector_dimensions=len(vectors[0]) if vectors else 0,
        first_vector_head=vectors[0][:5] if vectors else [],
    )
    store = make_store(config)
    try:
        store.ensure_collection(recreate=recreate)
        store.upsert(chunks, vectors)
    finally:
        store.close()
    _write_keyword_index(config, chunks, recreate=recreate)
    debug_breakpoint("ingest.after_upsert", collection=config.collection_name, chunk_count=len(chunks))
    return document_count, len(chunks)


def build_ingestion_chunks(batch: DoclingBatch, config: RagConfig, ingestion: DoclingIngestion) -> list:
    if config.chunk_strategy == "docling_hybrid":
        return batch.chunks
    if config.chunk_strategy == "adaptive_parent_child":
        return adaptive_parent_child_chunks(
            batch,
            ingestion.chunker.tokenizer.count_tokens,
            parent_tokens=config.parent_chunk_tokens,
            child_tokens=config.child_chunk_tokens,
            child_overlap=config.child_chunk_overlap,
        )
    raise ValueError(f"Unsupported RAG_CHUNK_STRATEGY: {config.chunk_strategy}")


def active_chunk_schema_version(config: RagConfig) -> str:
    if config.chunk_strategy == "adaptive_parent_child":
        return ADAPTIVE_CHUNK_SCHEMA_VERSION
    if config.chunk_strategy == "docling_hybrid":
        return DOCLING_CHUNK_SCHEMA_VERSION
    raise ValueError(f"Unsupported RAG_CHUNK_STRATEGY: {config.chunk_strategy}")


def search(query: str, config: RagConfig, top_k: int = 5, *, expand_parents: bool = True) -> list[SearchResult]:
    embeddings = make_embedding_client(config)
    store = make_store(config)
    try:
        store.ensure_collection(recreate=False)
        query_vector = embeddings.embed_query(query)
        debug_breakpoint("search.after_query_embedding", query=query, vector_dimensions=len(query_vector), vector_head=query_vector[:5])
        recall_k = max(top_k * 3, top_k) if expand_parents else top_k
        results = store.search(query_vector, top_k=recall_k)
    finally:
        store.close()
    debug_breakpoint("search.after_retrieval", query=query, result_count=len(results), first_result=results[0] if results else None)
    if not expand_parents:
        return results
    expanded = list(expand_parent_results(results, top_k))
    debug_breakpoint(
        "search.after_parent_expansion",
        query=query,
        result_count=len(expanded),
        first_result=expanded[0] if expanded else None,
    )
    return expanded


def answer(question: str, config: RagConfig, top_k: int = 5) -> tuple[str, list[SearchResult]]:
    results = search(question, config, top_k=top_k)
    debug_breakpoint("ask.after_retrieval", question=question, result_count=len(results), first_result=results[0] if results else None)
    if not _has_enough_relevance(results, config.min_score):
        top_score = results[0].score if results else 0.0
        response = (
            "本地知识库没有足够相关资料来回答这个问题。\n"
            f"最高检索分数是 {top_score:.2f}，低于当前阈值 {config.min_score:.2f}。\n"
            "你可以换一个和知识库更相关的问题，或调整 RAG_MIN_SCORE。"
        )
        debug_breakpoint("ask.low_score_rejected", question=question, top_score=top_score, min_score=config.min_score)
        return response, []

    chat = OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model)
    messages = build_rag_messages(question, results)
    debug_breakpoint("ask.before_llm", question=question, messages=messages)
    response = chat.complete(messages)
    debug_breakpoint("ask.after_llm", response=response)
    return response, results


def _has_enough_relevance(results: list[SearchResult], min_score: float) -> bool:
    return bool(results) and results[0].score >= min_score


def _write_keyword_index(config: RagConfig, chunks, recreate: bool) -> None:
    from obsidian_rag.v1.retrieval.keyword import KeywordIndex, keyword_index_path

    index = KeywordIndex(keyword_index_path(config.db_path, config.collection_name))
    if recreate:
        index.build(chunks)
    else:
        index.load()
        index.upsert(chunks)
    index.save()
