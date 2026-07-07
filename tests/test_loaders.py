from pathlib import Path

from obsidian_rag.loaders import load_markdown_file


def test_load_markdown_file_extracts_frontmatter_tags_links_and_title(tmp_path: Path):
    note = tmp_path / "Agent Memory.md"
    note.write_text(
        """---
title: Agent Memory Notes
tags:
  - agent
  - rag
---
# Long-term memory

Use [[RAG]] to recall #memory ideas.
""",
        encoding="utf-8",
    )

    document = load_markdown_file(note, vault_root=tmp_path)

    assert document.text.startswith("# Long-term memory")
    assert document.metadata["source"] == "Agent Memory.md"
    assert document.metadata["title"] == "Agent Memory Notes"
    assert document.metadata["tags"] == ["agent", "rag", "memory"]
    assert document.metadata["links"] == ["RAG"]


def test_load_markdown_file_uses_first_heading_when_frontmatter_has_no_title(tmp_path: Path):
    note = tmp_path / "rag.md"
    note.write_text("# RAG Flow\n\nIndex then retrieve.", encoding="utf-8")

    document = load_markdown_file(note, vault_root=tmp_path)

    assert document.metadata["title"] == "RAG Flow"
