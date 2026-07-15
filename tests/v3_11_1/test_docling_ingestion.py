from pathlib import Path

from obsidian_rag.docling_ingestion import DoclingIngestion


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
