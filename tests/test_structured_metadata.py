from obsidian_rag.structured_metadata import (
    extract_structured_sections,
    merge_structured_metadata,
    metadata_for_heading_path,
)


def test_extracts_bare_fenced_yaml_metadata_and_matches_docling_heading_path():
    markdown = """# VueUse

## VU-001：VueUse 定位

```
chunk_id: VU-001
title: VueUse 定位
category: 基础
tags: [vueuse, vue3]
source: https://vueuse.org/guide/
```

正文。
"""

    sections = extract_structured_sections(markdown)

    assert len(sections) == 1
    assert sections[0].metadata["chunk_id"] == "VU-001"
    assert metadata_for_heading_path(sections, ["VueUse", "VU-001：VueUse 定位"])["title"] == "VueUse 定位"

    merged = merge_structured_metadata({"source": "vueuse.md", "tags": ["vault"]}, sections[0].metadata)
    assert merged["source"] == "vueuse.md"
    assert merged["kb_source"] == "https://vueuse.org/guide/"
    assert merged["tags"] == ["vault", "vueuse", "vue3"]
    assert merged["topic"] == "VueUse 定位"


def test_uses_generic_numbered_heading_as_metadata_fallback():
    sections = extract_structured_sections("## RFC-9457：问题详情\n\n正文。")

    assert sections[0].metadata == {"chunk_id": "RFC-9457", "title": "问题详情"}
    assert metadata_for_heading_path([], ["RFC-9457：问题详情"])["chunk_id"] == "RFC-9457"
