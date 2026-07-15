"""Markdown 标题块中的业务 metadata 提取与传播。

业务 ``chunk_id`` 是内容作者提供的引用标识，不是系统生成的向量 ID。
本模块只把紧随二级标题块、且显式包含 ``chunk_id`` 的 fenced YAML 当作
业务 metadata，避免把普通示例 YAML 或文档级配置错误绑定到一个 chunk。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml


FENCED_YAML_RE = re.compile(r"```(?:ya?ml)?[ \t]*\n(?P<body>.*?)\n```", re.IGNORECASE | re.DOTALL)
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.+?)\s*#*\s*$", re.MULTILINE)
NUMBERED_HEADING_RE = re.compile(
    r"^(?P<identifier>[A-Za-z][A-Za-z0-9_]*-\d+(?:[A-Za-z0-9_-]*)?)(?:\s*[:：]\s*(?P<title>.+))?$"
)
SYSTEM_METADATA_KEYS = {
    "source",
    "node_id",
    "chunk_index",
    "document_parser",
    "chunk_schema_version",
    "heading_path",
    "page_numbers",
    "raw_chunk_text",
    "docling",
}


@dataclass(frozen=True)
class StructuredSection:
    """一个含业务 metadata 的 Markdown 二级标题块。"""

    start: int
    end: int
    heading: str
    metadata: dict[str, Any]
    aliases: tuple[str, ...]


def extract_structured_sections(markdown: str) -> list[StructuredSection]:
    """返回包含 YAML ``chunk_id`` 或通用编号 fallback 的二级标题块。"""

    headings = [match for match in HEADING_RE.finditer(markdown) if len(match.group("marks")) == 2]
    sections: list[StructuredSection] = []
    for index, heading_match in enumerate(headings):
        start = heading_match.start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        heading = _clean_heading(heading_match.group("title"))
        raw_metadata = _extract_yaml_metadata(markdown[heading_match.end() : end])
        metadata = raw_metadata or _fallback_heading_metadata(heading)
        if not metadata:
            continue
        sections.append(
            StructuredSection(
                start=start,
                end=end,
                heading=heading,
                metadata=metadata,
                aliases=_heading_aliases(heading, metadata),
            )
        )
    return sections


def merge_structured_metadata(base_metadata: dict[str, Any], structured_metadata: dict[str, Any]) -> dict[str, Any]:
    """把作者提供的 metadata 合并到 chunk metadata，保护系统字段。"""

    merged = dict(base_metadata)
    for raw_key, value in structured_metadata.items():
        if value is None:
            continue
        key = str(raw_key)
        if key == "source":
            source = _as_nonempty_string(value)
            if source:
                merged["kb_source"] = source
        elif key == "tags":
            merged["tags"] = _merge_unique(_as_tags(merged.get("tags")), _as_tags(value))
        elif key not in SYSTEM_METADATA_KEYS and _is_json_value(value):
            merged[key] = value

    if not _as_nonempty_string(structured_metadata.get("topic")):
        title = _as_nonempty_string(structured_metadata.get("title"))
        if title:
            merged["topic"] = title
    return merged


def metadata_for_heading_path(sections: list[StructuredSection], headings: list[str]) -> dict[str, Any]:
    """按最深 Docling heading 找到所属标题块的业务 metadata。"""

    aliases: dict[str, dict[str, Any]] = {}
    for section in sections:
        for alias in section.aliases:
            aliases[alias] = section.metadata
    for heading in reversed(headings):
        metadata = aliases.get(_normalize_heading(heading))
        if metadata is not None:
            return dict(metadata)
        fallback = _fallback_heading_metadata(_clean_heading(heading))
        if fallback:
            return fallback
    return {}


def _extract_yaml_metadata(section_body: str) -> dict[str, Any]:
    for match in FENCED_YAML_RE.finditer(section_body):
        try:
            parsed = yaml.safe_load(match.group("body")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(parsed, dict):
            continue
        if _as_nonempty_string(parsed.get("chunk_id")):
            return {str(key): value for key, value in parsed.items()}
    return {}


def _fallback_heading_metadata(heading: str) -> dict[str, Any]:
    match = NUMBERED_HEADING_RE.match(heading)
    if not match:
        return {}
    metadata: dict[str, Any] = {"chunk_id": match.group("identifier")}
    title = _as_nonempty_string(match.group("title"))
    if title:
        metadata["title"] = title
    return metadata


def _heading_aliases(heading: str, metadata: dict[str, Any]) -> tuple[str, ...]:
    values = [heading]
    match = NUMBERED_HEADING_RE.match(heading)
    if match:
        values.append(match.group("title") or "")
    values.append(_as_nonempty_string(metadata.get("title")) or "")
    normalized = [_normalize_heading(value) for value in values if _normalize_heading(value)]
    return tuple(dict.fromkeys(normalized))


def _clean_heading(value: str) -> str:
    return value.strip().rstrip("#").strip()


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", _clean_heading(value)).casefold()


def _as_nonempty_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _as_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lstrip("#")] if value.strip() else []
    if isinstance(value, list | tuple | set):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return [str(value).strip().lstrip("#")] if str(value).strip() else []


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in [*first, *second] if item))


def _is_json_value(value: object) -> bool:
    return isinstance(value, str | int | float | bool | list | dict)
