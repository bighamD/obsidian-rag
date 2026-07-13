from __future__ import annotations

import re

import yaml

from obsidian_rag.schema import SourceDocument, TextChunk


CHUNK_METADATA_RE = re.compile(r"```ya?ml\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)
KB_SECTION_HEADING_RE = re.compile(
    r"^##\s+(KB-[A-Za-z0-9][A-Za-z0-9_-]*)(?=\s|[:：]|$).*$",
    re.MULTILINE,
)


def chunk_document(document: SourceDocument, max_chars: int = 1200, overlap_chars: int = 150) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    text = document.text.strip()
    if not text:
        return []

    chunks: list[TextChunk] = []
    for section_text, section_chunk_id in _split_kb_sections(text):
        metadata = dict(document.metadata)
        metadata.update(_extract_chunk_metadata(section_text, metadata))
        if section_chunk_id is not None:
            # KB 标题定义语义边界和稳定 ID；YAML 补充 topic、tags 等元数据。
            metadata["chunk_id"] = section_chunk_id

        for chunk_text in _split_text(section_text, max_chars, overlap_chars):
            chunk_metadata = dict(metadata)
            chunk_metadata["chunk_index"] = len(chunks)
            chunks.append(TextChunk(text=chunk_text, metadata=chunk_metadata))
    return chunks


def chunk_documents(
    documents: list[SourceDocument], max_chars: int = 1200, overlap_chars: int = 150
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars))
    return chunks


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_paragraph(paragraph, max_chars, overlap_chars))
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.strip())
            current = _with_overlap(current, paragraph, overlap_chars)

    if current:
        chunks.append(current.strip())
    return chunks


def _split_kb_sections(text: str) -> list[tuple[str, str | None]]:
    """按二级 KB 标题切分，避免相邻知识块共享或错配 metadata。"""

    headings = list(KB_SECTION_HEADING_RE.finditer(text))
    if not headings:
        return [(text, None)]

    sections: list[tuple[str, str | None]] = []
    prefix = text[: headings[0].start()].strip()
    if prefix:
        sections.append((prefix, None))

    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.start() : end].strip()
        if section:
            sections.append((section, heading.group(1)))
    return sections


def _split_long_paragraph(paragraph: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        chunks.append(paragraph[start:end].strip())
        if end == len(paragraph):
            break
        start = max(0, end - overlap_chars)
    return chunks


def _with_overlap(previous: str, next_paragraph: str, overlap_chars: int) -> str:
    if overlap_chars == 0:
        return next_paragraph
    overlap = previous[-overlap_chars:].strip()
    return f"{overlap}\n\n{next_paragraph}".strip()


def _extract_chunk_metadata(text: str, base_metadata: dict[str, object]) -> dict[str, object]:
    match = CHUNK_METADATA_RE.search(text)
    if not match:
        return {}

    try:
        parsed = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    metadata: dict[str, object] = {}
    for key, value in parsed.items():
        if value is None:
            continue
        normalized_key = str(key)
        if normalized_key == "source":
            metadata["kb_source"] = str(value)
        elif normalized_key == "tags":
            metadata["tags"] = _merge_unique(_as_list(base_metadata.get("tags")), _as_list(value))
        else:
            metadata[normalized_key] = value
    return metadata


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lstrip("#")] if value.strip() else []
    if isinstance(value, list | tuple | set):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return [str(value).strip().lstrip("#")] if str(value).strip() else []


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        if item and item not in seen:
            merged.append(item)
            seen.add(item)
    return merged
