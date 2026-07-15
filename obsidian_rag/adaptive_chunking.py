from __future__ import annotations

import uuid
from collections.abc import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.docling_ingestion import DoclingBatch, DoclingConversion
from obsidian_rag.schema import TextChunk
from obsidian_rag.structured_metadata import (
    extract_structured_sections,
    merge_structured_metadata,
    metadata_for_heading_path,
)


ADAPTIVE_CHUNK_SCHEMA_VERSION = "parent-child-v1"
ADAPTIVE_CHUNK_STRATEGY = "adaptive_parent_child"


def adaptive_parent_child_chunks(
    batch: DoclingBatch,
    count_tokens: Callable[[str], int],
    *,
    parent_tokens: int,
    child_tokens: int,
    child_overlap: int,
) -> list[TextChunk]:
    """把 Docling 原子块聚合为结构 parent，仅在超长时生成多个检索 child。"""

    if parent_tokens <= child_tokens:
        raise ValueError("RAG_PARENT_CHUNK_TOKENS must be larger than RAG_CHILD_CHUNK_TOKENS")
    if child_overlap < 0 or child_overlap >= child_tokens:
        raise ValueError("RAG_CHILD_CHUNK_OVERLAP must be between 0 and child chunk size")

    parent_splitter = _splitter(parent_tokens, 0, count_tokens)
    chunks: list[TextChunk] = []
    chunk_index = 0
    for conversion in batch.conversions:
        raw_chunks = [chunk for chunk in batch.chunks if chunk.metadata.get("source") == conversion.source]
        structured_sections = extract_structured_sections(conversion.markdown)
        groups = _structural_groups(raw_chunks)
        debug_breakpoint(
            "adaptive.after_groups",
            source=conversion.source,
            raw_block_count=len(raw_chunks),
            group_count=len(groups),
            first_group=groups[0] if groups else [],
        )
        for group_index, group in enumerate(groups):
            heading_path = _group_heading_path(group)
            rendered = _render_group(group)
            if not rendered:
                continue
            parent_parts = [rendered] if count_tokens(rendered) <= parent_tokens else parent_splitter.split_text(rendered)
            for parent_index, parent_text in enumerate(parent_parts):
                parent_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{conversion.source}:parent:{group_index}:{parent_index}:{parent_text[:200]}",
                    )
                )
                if count_tokens(parent_text) <= child_tokens:
                    child_parts = [parent_text]
                else:
                    breadcrumb = " > ".join(heading_path)
                    available_tokens = max(32, child_tokens - count_tokens(breadcrumb) - 2)
                    child_splitter = _splitter(
                        available_tokens,
                        min(child_overlap, available_tokens - 1),
                        count_tokens,
                    )
                    child_parts = child_splitter.split_text(parent_text)
                for child_index, child_text in enumerate(child_parts):
                    embedding_text = _contextualize_child(child_text, parent_text, heading_path, len(child_parts))
                    node_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{parent_id}:child:{child_index}:{embedding_text[:200]}",
                        )
                    )
                    metadata = _metadata(
                        conversion=conversion,
                        group=group,
                        structured_sections=structured_sections,
                        heading_path=heading_path,
                        parent_id=parent_id,
                        parent_text=parent_text,
                        parent_tokens=count_tokens(parent_text),
                        child_text=child_text,
                        child_tokens=count_tokens(embedding_text),
                        child_index=child_index,
                        chunk_index=chunk_index,
                        node_id=node_id,
                    )
                    chunks.append(TextChunk(text=embedding_text, metadata=metadata))
                    chunk_index += 1
    debug_breakpoint(
        "adaptive.after_chunks",
        parent_count=len({chunk.metadata.get("parent_id") for chunk in chunks}),
        child_count=len(chunks),
        first_chunk=chunks[0] if chunks else None,
    )
    return chunks


def _splitter(chunk_size: int, overlap: int, count_tokens: Callable[[str], int]) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=count_tokens,
        separators=["\n# ", "\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", ". ", " ", ""],
        keep_separator=True,
    )


def _structural_groups(chunks: list[TextChunk]) -> list[list[TextChunk]]:
    if not chunks:
        return []
    anchor_depth = _anchor_depth(chunks)
    groups: list[list[TextChunk]] = []
    previous_key: tuple[str, ...] | None = None
    for chunk in chunks:
        path = tuple(str(item) for item in chunk.metadata.get("heading_path", []))
        key = path[: anchor_depth + 1] if anchor_depth >= 0 and len(path) > anchor_depth else ("__preamble__", *path)
        if key != previous_key:
            groups.append([])
            previous_key = key
        groups[-1].append(chunk)
    return groups


def _anchor_depth(chunks: list[TextChunk]) -> int:
    paths = [tuple(str(item) for item in chunk.metadata.get("heading_path", [])) for chunk in chunks]
    max_depth = max((len(path) for path in paths), default=0)
    for depth in range(max_depth):
        prefixes = {path[: depth + 1] for path in paths if len(path) > depth}
        if len(prefixes) >= 2:
            return depth
    return max_depth - 1


def _group_heading_path(group: list[TextChunk]) -> list[str]:
    paths = [[str(item) for item in chunk.metadata.get("heading_path", [])] for chunk in group]
    if not paths:
        return []
    common = list(paths[0])
    for path in paths[1:]:
        common = common[: _common_prefix_length(common, path)]
    return common or list(paths[0])


def _render_group(group: list[TextChunk]) -> str:
    parts: list[str] = []
    previous_path: list[str] = []
    for chunk in group:
        path = [str(item) for item in chunk.metadata.get("heading_path", [])]
        common = _common_prefix_length(previous_path, path)
        for depth, heading in enumerate(path[common:], start=common):
            parts.append(f"{'#' * min(depth + 1, 6)} {heading}")
        raw_text = str(chunk.metadata.get("raw_chunk_text") or chunk.text).strip()
        if raw_text:
            parts.append(raw_text)
        previous_path = path
    return "\n\n".join(parts).strip()


def _common_prefix_length(first: list[str], second: list[str]) -> int:
    length = 0
    for left, right in zip(first, second):
        if left != right:
            break
        length += 1
    return length


def _contextualize_child(child_text: str, parent_text: str, heading_path: list[str], child_count: int) -> str:
    if child_count == 1:
        return parent_text
    breadcrumb = " > ".join(heading_path)
    return f"{breadcrumb}\n\n{child_text}" if breadcrumb else child_text


def _metadata(
    *,
    conversion: DoclingConversion,
    group: list[TextChunk],
    structured_sections,
    heading_path: list[str],
    parent_id: str,
    parent_text: str,
    parent_tokens: int,
    child_text: str,
    child_tokens: int,
    child_index: int,
    chunk_index: int,
    node_id: str,
) -> dict:
    pages = sorted(
        {
            int(page)
            for chunk in group
            for page in chunk.metadata.get("page_numbers", [])
        }
    )
    metadata = {
        "source": conversion.source,
        "title": conversion.title,
        "chunk_index": chunk_index,
        "node_id": node_id,
        "parent_id": parent_id,
        "child_index": child_index,
        "document_parser": "docling",
        "chunk_strategy": ADAPTIVE_CHUNK_STRATEGY,
        "chunk_schema_version": ADAPTIVE_CHUNK_SCHEMA_VERSION,
        "heading_path": heading_path,
        "page_numbers": pages,
        "raw_chunk_text": child_text,
        "parent_text": parent_text,
        "parent_token_count": parent_tokens,
        "child_token_count": child_tokens,
    }
    metadata = merge_structured_metadata(
        metadata,
        metadata_for_heading_path(structured_sections, heading_path),
    )
    if heading_path:
        metadata.setdefault("topic", heading_path[-1])
    return metadata
