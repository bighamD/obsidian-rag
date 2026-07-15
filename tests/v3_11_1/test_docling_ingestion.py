from pathlib import Path

from obsidian_rag.docling_ingestion import DoclingConversion, DoclingIngestion


class FakeMeta:
    def export_json_dict(self):
        return {
            "headings": ["KB-072：鸡肉处理"],
            "doc_items": [{"prov": [{"page_no": 3}]}],
        }


class FakeChunk:
    text = "不建议清洗生鸡肉。"
    meta = FakeMeta()


class FakeChunker:
    def chunk(self, dl_doc):
        assert isinstance(dl_doc, FakeDocument)
        return [FakeChunk()]

    def contextualize(self, chunk):
        return "KB-072：鸡肉处理\n不建议清洗生鸡肉。"


class FakeDocument:
    name = "食品安全"
    pages = {1: object(), 2: object(), 3: object()}

    def export_to_markdown(self):
        return "# KB-072：鸡肉处理\n\n不建议清洗生鸡肉。"

    def iterate_items(self):
        return iter([("title", 0), ("paragraph", 1)])


class FakeResult:
    document = FakeDocument()
    status = "success"


class FakeConverter:
    def convert(self, path):
        assert Path(path).name == "food.md"
        return FakeResult()


def test_docling_adapter_maps_framework_chunks_to_text_chunks(tmp_path: Path):
    source = tmp_path / "food.md"
    source.write_text("placeholder", encoding="utf-8")
    adapter = DoclingIngestion(
        tokenizer_model="fake",
        max_tokens=512,
        converter=FakeConverter(),
        chunker=FakeChunker(),
    )

    conversion = adapter.convert_file(source, tmp_path)
    chunks = adapter.chunk_conversion(conversion)

    assert conversion.source == "food.md"
    assert conversion.page_count == 3
    assert len(chunks) == 1
    assert chunks[0].text.startswith("KB-072")
    assert chunks[0].metadata["chunk_id"] == "KB-072"
    assert chunks[0].metadata["page_numbers"] == [3]
    assert chunks[0].metadata["chunk_schema_version"] == "docling-v1"


class FakeVueMeta:
    def export_json_dict(self):
        return {
            "headings": ["VueUse Core 使用方式与配置知识库", "VU-001：VueUse 定位", "知识内容"],
            "doc_items": [{"prov": [{"page_no": 1}]}],
        }


class FakeVueChunk:
    text = "VueUse 是工具函数集合。"
    meta = FakeVueMeta()


class FakeVueChunker:
    def chunk(self, dl_doc):
        return [FakeVueChunk()]

    def contextualize(self, chunk):
        return "VU-001：VueUse 定位\nVueUse 是工具函数集合。"


class FakePlainMeta:
    def export_json_dict(self):
        return {"headings": ["Plain", "普通标题"], "doc_items": []}


class FakePlainChunk:
    text = "正文。"
    meta = FakePlainMeta()


class FakePlainChunker:
    def chunk(self, dl_doc):
        return [FakePlainChunk()]

    def contextualize(self, chunk):
        return "普通标题\n正文。"


def test_docling_adapter_propagates_generic_yaml_metadata_by_heading_path():
    markdown = """# VueUse Core 使用方式与配置知识库

## VU-001：VueUse 定位

```
chunk_id: VU-001
title: VueUse 定位
category: 基础
tags: [vueuse, composition-api]
source: https://vueuse.org/guide/
```

### 知识内容

VueUse 是工具函数集合。
"""
    conversion = DoclingConversion(
        source="vueuse.md",
        title="VueUse Core 使用方式与配置知识库",
        status="success",
        page_count=1,
        item_count=3,
        markdown=markdown,
        document=object(),
    )
    adapter = DoclingIngestion(
        tokenizer_model="fake",
        max_tokens=512,
        converter=object(),
        chunker=FakeVueChunker(),
    )

    chunks = adapter.chunk_conversion(conversion)

    assert len(chunks) == 1
    metadata = chunks[0].metadata
    assert metadata["node_id"]
    assert metadata["chunk_id"] == "VU-001"
    assert metadata["title"] == "VueUse 定位"
    assert metadata["topic"] == "VueUse 定位"
    assert metadata["category"] == "基础"
    assert metadata["tags"] == ["vueuse", "composition-api"]
    assert metadata["source"] == "vueuse.md"
    assert metadata["kb_source"] == "https://vueuse.org/guide/"


def test_docling_adapter_does_not_invent_chunk_id_without_structured_metadata():
    conversion = DoclingConversion(
        source="plain.md",
        title="Plain",
        status="success",
        page_count=0,
        item_count=1,
        markdown="# Plain\n\n## 普通标题\n\n正文。",
        document=object(),
    )
    adapter = DoclingIngestion(
        tokenizer_model="fake",
        max_tokens=512,
        converter=object(),
        chunker=FakePlainChunker(),
    )

    chunks = adapter.chunk_conversion(conversion)

    assert chunks[0].metadata["node_id"]
    assert "chunk_id" not in chunks[0].metadata
