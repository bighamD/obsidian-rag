from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag.cli import run_documents3111
from obsidian_rag.config import RagConfig
from obsidian_rag.docling_ingestion import DoclingBatch, DoclingConversion
from obsidian_rag.schema import TextChunk
from obsidian_rag.v3_11_1.app import app
from obsidian_rag.v3_11_1.dependencies import get_docling_service
from obsidian_rag.v3_11_1.schemas import DoclingPathRequest
from obsidian_rag.v3_11_1.service import DoclingLearningService


def _config(path: Path) -> RagConfig:
    return RagConfig(
        api_key="test",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=8,
        embedding_provider="hash",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=path / "qdrant",
        collection_name="test",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.0,
        vault_path=path / "food.md",
        document_parser="docling",
        docling_tokenizer_model="fake-tokenizer",
    )


class FakeAdapter:
    def __init__(self, source: Path):
        self.source = source
        self.conversion = DoclingConversion(
            source=source.name,
            title="Food",
            status="success",
            page_count=1,
            item_count=2,
            markdown="# Food\n\nSafe handling.",
            document=object(),
        )
        self.chunk = TextChunk(
            text="Food\nSafe handling.",
            metadata={
                "node_id": "n1",
                "source": source.name,
                "heading_path": ["Food"],
                "page_numbers": [1],
                "raw_chunk_text": "Safe handling.",
            },
        )

    def convert_file(self, path):
        return self.conversion

    def convert_and_chunk_path(self, path):
        return DoclingBatch(conversions=[self.conversion], chunks=[self.chunk], errors=[])


def test_service_and_api_preview_docling_chunks(tmp_path: Path):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")
    service = DoclingLearningService(_config(tmp_path), adapter=FakeAdapter(source))

    response = service.chunks(DoclingPathRequest(path=str(source)))
    assert response.documents[0].title == "Food"
    assert response.chunks[0].raw_text == "Safe handling."

    app.dependency_overrides[get_docling_service] = lambda: service
    try:
        api_response = TestClient(app).post("/documents/chunks", json={"path": str(source)})
    finally:
        app.dependency_overrides.clear()
    assert api_response.status_code == 200
    assert api_response.json()["chunks"][0]["node_id"] == "n1"


def test_cli_prints_v3_11_1_json(tmp_path: Path, capsys):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")
    service = DoclingLearningService(_config(tmp_path), adapter=FakeAdapter(source))

    run_documents3111("chunks", _config(tmp_path), path=source, service=service)

    assert '"tokenizer_model": "fake-tokenizer"' in capsys.readouterr().out
