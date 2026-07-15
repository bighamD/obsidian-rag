from pathlib import Path

from fastapi.testclient import TestClient

from obsidian_rag.cli import run_chunking3112_compare
from obsidian_rag.config import RagConfig
from obsidian_rag.docling_ingestion import DoclingConversion
from obsidian_rag.v3_11_2.app import app
from obsidian_rag.v3_11_2.dependencies import get_framework_comparison_service
from obsidian_rag.v3_11_2.frameworks import FrameworkChunk, FrameworkHit, FrameworkRun
from obsidian_rag.v3_11_2.schemas import FrameworkCompareRequest
from obsidian_rag.v3_11_2.service import FrameworkComparisonService


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
        vault_path=path / "manual.md",
    )


class FakeDocling:
    def convert_file(self, path):
        return DoclingConversion(
            source=Path(path).name,
            title="Manual",
            status="success",
            page_count=0,
            item_count=2,
            markdown="# Deploy\n\nRollback when health checks fail.",
            document=object(),
        )


class FakeEmbedding:
    def embed_texts(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0]


def _run(framework: str, strategy: str) -> FrameworkRun:
    chunk = FrameworkChunk(node_id=f"{strategy}-c1", text="Rollback context", metadata={"source": "manual.md"})
    hit = FrameworkHit(
        node_id=f"{strategy}-h1",
        text="Rollback context",
        score=0.9,
        metadata={"source": "manual.md"},
        hit_kind="returned_parent",
    )
    return FrameworkRun(
        framework=framework,
        strategy=strategy,
        build_ms=1.2,
        chunk_count=1,
        average_chars=16.0,
        max_chars=16,
        chunks=[chunk],
        hits=[hit],
    )


def test_service_api_and_cli_compare_three_framework_strategies(tmp_path: Path, monkeypatch, capsys):
    source = tmp_path / "manual.md"
    source.write_text("# Deploy", encoding="utf-8")
    monkeypatch.setattr("obsidian_rag.v3_11_2.service.run_langchain_parent", lambda *args: _run("langchain", "recursive_parent"))
    monkeypatch.setattr(
        "obsidian_rag.v3_11_2.service.run_llamaindex_hierarchical",
        lambda *args: _run("llamaindex", "hierarchical_auto_merge"),
    )
    monkeypatch.setattr(
        "obsidian_rag.v3_11_2.service.run_llamaindex_semantic",
        lambda *args: _run("llamaindex", "semantic_splitter"),
    )
    service = FrameworkComparisonService(_config(tmp_path), docling=FakeDocling(), embedding_client=FakeEmbedding())
    request = FrameworkCompareRequest(path=str(source), query="how to rollback?")

    response = service.compare(request)
    assert [item.strategy for item in response.results] == [
        "recursive_parent",
        "hierarchical_auto_merge",
        "semantic_splitter",
    ]

    app.dependency_overrides[get_framework_comparison_service] = lambda: service
    try:
        api_response = TestClient(app).post("/frameworks/compare", json=request.model_dump())
    finally:
        app.dependency_overrides.clear()
    assert api_response.status_code == 200
    assert len(api_response.json()["results"]) == 3

    run_chunking3112_compare(_config(tmp_path), "how to rollback?", path=source, service=service)
    assert '"semantic_splitter"' in capsys.readouterr().out
