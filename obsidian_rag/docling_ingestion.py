from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from obsidian_rag.schema import TextChunk


DOCLING_CHUNK_SCHEMA_VERSION = "docling-v1"
SUPPORTED_SUFFIXES = {
    ".adoc",
    ".asciidoc",
    ".bmp",
    ".csv",
    ".docx",
    ".htm",
    ".html",
    ".jpeg",
    ".jpg",
    ".md",
    ".markdown",
    ".pdf",
    ".png",
    ".pptx",
    ".tif",
    ".tiff",
    ".webp",
    ".xlsx",
}
KB_ID_RE = re.compile(r"\b(KB-[A-Za-z0-9][A-Za-z0-9_-]*)\b")


@dataclass(frozen=True)
class DoclingConversion:
    """一次 Docling 转换结果；document 是框架原对象，API 只暴露摘要和 Markdown。"""

    source: str
    title: str
    status: str
    page_count: int
    item_count: int
    markdown: str
    document: Any


@dataclass(frozen=True)
class DoclingBatch:
    """目录转换结果，允许个别文件失败但保留成功 chunks。"""

    conversions: list[DoclingConversion]
    chunks: list[TextChunk]
    errors: list[str]


class DoclingIngestion:
    """Docling 的薄适配层：Converter/HybridChunker -> 本仓库 TextChunk。"""

    def __init__(
        self,
        tokenizer_model: str,
        max_tokens: int,
        *,
        converter: Any | None = None,
        chunker: Any | None = None,
    ):
        if converter is None or chunker is None:
            converter, chunker = _build_docling(tokenizer_model, max_tokens)
        self.converter = converter
        self.chunker = chunker

    def convert_file(self, path: Path, root: Path | None = None) -> DoclingConversion:
        resolved = path.expanduser().resolve()
        result = self.converter.convert(resolved)
        document = result.document
        source = _relative_source(resolved, (root or resolved.parent).expanduser().resolve())
        markdown = str(document.export_to_markdown())
        return DoclingConversion(
            source=source,
            title=str(getattr(document, "name", None) or resolved.stem),
            status=str(getattr(result, "status", "success")),
            page_count=len(getattr(document, "pages", {}) or {}),
            item_count=_item_count(document),
            markdown=markdown,
            document=document,
        )

    def chunk_conversion(self, conversion: DoclingConversion) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for index, chunk in enumerate(self.chunker.chunk(dl_doc=conversion.document)):
            contextualized = str(self.chunker.contextualize(chunk=chunk)).strip()
            raw_text = str(chunk.text).strip()
            docling_meta = _export_meta(chunk.meta)
            headings = [str(value) for value in docling_meta.get("headings", [])]
            page_numbers = sorted(_collect_page_numbers(docling_meta))
            node_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{conversion.source}:{index}:{contextualized[:160]}",
                )
            )
            metadata: dict[str, Any] = {
                "source": conversion.source,
                "title": conversion.title,
                "chunk_index": index,
                "node_id": node_id,
                "document_parser": "docling",
                "chunk_schema_version": DOCLING_CHUNK_SCHEMA_VERSION,
                "heading_path": headings,
                "page_numbers": page_numbers,
                "raw_chunk_text": raw_text,
                "docling": docling_meta,
            }
            kb_match = KB_ID_RE.search("\n".join([*headings, contextualized]))
            if kb_match:
                metadata["chunk_id"] = kb_match.group(1)
            if headings:
                metadata["topic"] = headings[-1]
            chunks.append(TextChunk(text=contextualized, metadata=metadata))
        return chunks

    def convert_and_chunk_path(self, path: Path) -> DoclingBatch:
        root = path.expanduser().resolve()
        files = _document_files(root)
        vault_root = root.parent if root.is_file() else root
        conversions: list[DoclingConversion] = []
        chunks: list[TextChunk] = []
        errors: list[str] = []
        for file_path in files:
            try:
                conversion = self.convert_file(file_path, vault_root)
                conversions.append(conversion)
                chunks.extend(self.chunk_conversion(conversion))
            except Exception as exc:
                errors.append(f"{file_path}: {type(exc).__name__}: {exc}")
        return DoclingBatch(conversions=conversions, chunks=chunks, errors=errors)


def _build_docling(tokenizer_model: str, max_tokens: int) -> tuple[Any, Any]:
    try:
        from docling.document_converter import DocumentConverter
        from docling_core.transforms.chunker import HybridChunker
        from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Docling 依赖未安装，请执行 `pip install -e .` 后重试。"
        ) from exc

    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=tokenizer_model,
        max_tokens=max_tokens,
    )
    return DocumentConverter(), HybridChunker(tokenizer=tokenizer)


def _document_files(path: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"Document path does not exist: {path}")
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Docling unsupported file type: {path.suffix}")
        return [path]
    files = [
        item
        for item in sorted(path.rglob("*"))
        if item.is_file() and not item.name.startswith(".") and item.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    if not files:
        raise ValueError(f"No Docling-supported documents found under: {path}")
    return files


def _relative_source(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _item_count(document: Any) -> int:
    iterator = getattr(document, "iterate_items", None)
    return sum(1 for _ in iterator()) if callable(iterator) else 0


def _export_meta(meta: Any) -> dict[str, Any]:
    if hasattr(meta, "export_json_dict"):
        return dict(meta.export_json_dict())
    if hasattr(meta, "model_dump"):
        return dict(meta.model_dump(mode="json", exclude_none=True))
    return {}


def _collect_page_numbers(value: Any) -> set[int]:
    pages: set[int] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"page_no", "page_number"} and isinstance(item, int):
                pages.add(item)
            else:
                pages.update(_collect_page_numbers(item))
    elif isinstance(value, list):
        for item in value:
            pages.update(_collect_page_numbers(item))
    return pages
