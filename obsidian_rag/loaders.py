from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml
from pypdf import PdfReader

from obsidian_rag.schema import SourceDocument

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
TAG_RE = re.compile(r"(?<!\w)#([\w\-/\u4e00-\u9fff]+)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def load_documents(path: Path) -> list[SourceDocument]:
    root = path.expanduser().resolve()
    if root.is_file():
        return [_load_file(root, root.parent)]

    documents: list[SourceDocument] = []
    for file_path in sorted(root.rglob("*")):
        if file_path.name.startswith(".") or not file_path.is_file():
            continue
        if file_path.suffix.lower() in {".md", ".markdown", ".pdf"}:
            documents.append(_load_file(file_path, root))
    return documents


def _load_file(path: Path, vault_root: Path) -> SourceDocument:
    if path.suffix.lower() in {".md", ".markdown"}:
        return load_markdown_file(path, vault_root)
    if path.suffix.lower() == ".pdf":
        return load_pdf_file(path, vault_root)
    raise ValueError(f"Unsupported file type: {path}")


def load_markdown_file(path: Path, vault_root: Path) -> SourceDocument:
    raw_text = path.read_text(encoding="utf-8")
    frontmatter, text = _extract_frontmatter(raw_text)
    metadata = _base_metadata(path, vault_root)

    title = frontmatter.get("title") or _first_heading(text) or path.stem
    metadata["title"] = str(title)
    metadata["tags"] = _merge_unique(_normalize_tags(frontmatter.get("tags")), _extract_tags(text))
    metadata["links"] = _extract_wikilinks(text)
    return SourceDocument(text=text.strip(), metadata=metadata)


def load_pdf_file(path: Path, vault_root: Path) -> SourceDocument:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    metadata = _base_metadata(path, vault_root)
    metadata["title"] = path.stem
    metadata["tags"] = []
    metadata["links"] = []
    return SourceDocument(text=text.strip(), metadata=metadata)


def _extract_frontmatter(raw_text: str) -> tuple[dict[str, object], str]:
    match = FRONTMATTER_RE.match(raw_text)
    if not match:
        return {}, raw_text

    parsed = yaml.safe_load(match.group(1)) or {}
    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, raw_text[match.end() :]


def _base_metadata(path: Path, vault_root: Path) -> dict[str, object]:
    resolved_root = vault_root.expanduser().resolve()
    resolved_path = path.expanduser().resolve()
    try:
        source = str(resolved_path.relative_to(resolved_root))
    except ValueError:
        source = str(resolved_path)
    return {"source": source}


def _first_heading(text: str) -> str | None:
    match = HEADING_RE.search(text)
    return match.group(1).strip() if match else None


def _normalize_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lstrip("#")] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(tag).strip().lstrip("#") for tag in value if str(tag).strip()]
    return []


def _extract_tags(text: str) -> list[str]:
    return [match.group(1) for match in TAG_RE.finditer(text)]


def _extract_wikilinks(text: str) -> list[str]:
    return _merge_unique([], [match.group(1).strip() for match in WIKILINK_RE.finditer(text)])


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        if item and item not in seen:
            merged.append(item)
            seen.add(item)
    return merged
