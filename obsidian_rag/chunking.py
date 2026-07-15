from __future__ import annotations

from obsidian_rag.schema import SourceDocument, TextChunk
from obsidian_rag.structured_metadata import extract_structured_sections, merge_structured_metadata


def chunk_document(document: SourceDocument, max_chars: int = 1200, overlap_chars: int = 150) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    text = document.text.strip()
    if not text:
        return []

    chunks: list[TextChunk] = []
    for section_text, section_metadata in _split_structured_sections(text):
        metadata = dict(document.metadata)
        metadata = merge_structured_metadata(metadata, section_metadata)

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


def _split_structured_sections(text: str) -> list[tuple[str, dict[str, object]]]:
    """按含结构化 metadata 的二级标题块切分，保留无结构文档的旧行为。"""

    structured_sections = extract_structured_sections(text)
    if not structured_sections:
        return [(text, {})]

    sections: list[tuple[str, dict[str, object]]] = []
    cursor = 0
    for structured_section in structured_sections:
        prefix = text[cursor : structured_section.start].strip()
        if prefix:
            sections.append((prefix, {}))
        section_text = text[structured_section.start : structured_section.end].strip()
        if section_text:
            sections.append((section_text, dict(structured_section.metadata)))
        cursor = structured_section.end
    suffix = text[cursor:].strip()
    if suffix:
        sections.append((suffix, {}))
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
