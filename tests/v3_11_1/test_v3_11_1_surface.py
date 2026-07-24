from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag.cli import run_documents3111
from obsidian_rag.config import RagConfig
from obsidian_rag.docling_ingestion import DoclingBatch, DoclingConversion
from obsidian_rag.schema import TextChunk
from obsidian_rag.v3_11_1.app import app
from obsidian_rag.v3_11_1.dependencies import get_docling_service
from obsidian_rag.v3_11_1 import service as docling_service_module
from obsidian_rag.v3_11_1.schemas import (
    DoclingIngestRequest,
    DoclingIngestResponse,
    DoclingPathRequest,
    DoclingSearchRequest,
)
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
        min_score=0.0,
        vault_path=path / "food.md",
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
        self.chunker = type(
            "Chunker",
            (),
            {"tokenizer": type("Tokenizer", (), {"count_tokens": staticmethod(lambda text: len(text))})()},
        )()

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
    assert response.chunks[0].raw_text.endswith("Safe handling.")
    assert response.chunks[0].parent_text == "# Food\n\nSafe handling."

    app.dependency_overrides[get_docling_service] = lambda: service
    try:
        api_response = TestClient(app).post("/documents/chunks", json={"path": str(source)})
    finally:
        app.dependency_overrides.clear()
    assert api_response.status_code == 200
    assert api_response.json()["chunks"][0]["node_id"]
    assert api_response.json()["chunks"][0]["parent_id"]


def test_cli_prints_v3_11_1_json(tmp_path: Path, capsys):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")
    service = DoclingLearningService(_config(tmp_path), adapter=FakeAdapter(source))

    run_documents3111("chunks", _config(tmp_path), path=source, service=service)

    assert '"tokenizer_model": "fake-tokenizer"' in capsys.readouterr().out


def test_docling_ingest_uses_request_collection(tmp_path: Path, monkeypatch):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")
    service = DoclingLearningService(_config(tmp_path), adapter=FakeAdapter(source))
    captured = {}

    def fake_ingest(path, config, recreate):
        captured.update(path=path, collection=config.collection_name, recreate=recreate)
        return 1, 2

    monkeypatch.setattr(docling_service_module, "ingest_path", fake_ingest)

    response = service.ingest(
        DoclingIngestRequest(path=str(source), collection="food_safety", recreate=True)
    )

    assert captured == {"path": source, "collection": "food_safety", "recreate": True}
    assert response.collection == "food_safety"


def test_docling_ingest_api_forwards_collection():
    class CapturingService:
        request = None

        def ingest(self, request):
            self.request = request
            return DoclingIngestResponse(
                document_count=1,
                chunk_count=2,
                parser="docling",
                chunk_schema_version="docling-v1",
                recreated=request.recreate,
                collection=request.collection or "obsidian_notes",
            )

    service = CapturingService()
    app.dependency_overrides[get_docling_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/documents/ingest",
            json={"collection": "food_safety", "recreate": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.request.collection == "food_safety"
    assert response.json()["collection"] == "food_safety"


def test_docling_search_uses_request_collection(tmp_path: Path, monkeypatch):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")
    captured = {}

    class FakeRetrievalService:
        def __init__(self, config):
            captured["default_collection"] = config.collection_name

        def collection_name(self, collection=None):
            return collection or captured["default_collection"]

        def search(self, query, top_k=5, mode="hybrid", collection=None):
            captured.update(query=query, top_k=top_k, mode=mode, collection=collection)
            return [
                type(
                    "Result",
                    (),
                    {
                        "score": 0.8,
                        "chunk": TextChunk(
                            text="食品安全结果",
                            metadata={"source": "food.md", "node_id": "n1", "heading_path": [], "page_numbers": []},
                        ),
                    },
                )()
            ]

    monkeypatch.setattr(docling_service_module, "RetrievalService", FakeRetrievalService)
    response = DoclingLearningService(_config(tmp_path)).search(
        DoclingSearchRequest(query="鸡肉", collection="food_safety")
    )

    assert captured["collection"] == "food_safety"
    assert response.collection == "food_safety"


def test_docling_cli_forwards_collection_to_ingest_request(tmp_path: Path, capsys):
    source = tmp_path / "food.md"
    source.write_text("# Food", encoding="utf-8")

    class CapturingService:
        request = None

        def ingest(self, request):
            self.request = request
            return DoclingIngestResponse(
                document_count=1,
                chunk_count=2,
                parser="docling",
                chunk_schema_version="docling-v1",
                recreated=request.recreate,
                collection=request.collection or "obsidian_notes",
            )

    service = CapturingService()
    run_documents3111(
        "ingest",
        _config(tmp_path),
        path=source,
        recreate=True,
        collection="food_safety",
        service=service,
    )

    assert service.request.collection == "food_safety"
    assert '"collection": "food_safety"' in capsys.readouterr().out
