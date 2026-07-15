from pathlib import Path

from obsidian_rag.config import RagConfig, with_collection
from obsidian_rag.pipeline import ingest_path
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v1.retrieval.keyword import KeywordIndex, keyword_index_path
from obsidian_rag.v1.services import retrieval_service as retrieval_module
from obsidian_rag.v1.services.retrieval_service import RetrievalService


def _config(tmp_path: Path) -> RagConfig:
    return RagConfig(
        api_key="test",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=8,
        embedding_provider="hash",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=tmp_path / "qdrant",
        collection_name="obsidian_notes",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.0,
        vault_path=None,
    )


def _save_keyword_index(path: Path, source: str, text: str) -> None:
    index = KeywordIndex(path)
    index.build([TextChunk(text=text, metadata={"source": source, "topic": source})])
    index.save()


def test_hybrid_retrieval_uses_same_explicit_collection_for_dense_and_keyword(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    _save_keyword_index(keyword_index_path(config.db_path, "food_safety"), "food.md", "食品安全 鸡肉 清洗")
    _save_keyword_index(keyword_index_path(config.db_path, "recipes"), "recipes.md", "菜谱 番茄 意面")
    dense_collections: list[str] = []

    def fake_dense_search(query, request_config, top_k=5):
        dense_collections.append(request_config.collection_name)
        return [
            SearchResult(
                chunk=TextChunk(
                    text=f"{request_config.collection_name} dense hit",
                    metadata={"source": f"{request_config.collection_name}.md"},
                ),
                score=0.9,
            )
        ]

    monkeypatch.setattr(retrieval_module, "dense_search", fake_dense_search)
    service = RetrievalService(config)

    recipe_results = service.search("菜谱 番茄", mode="hybrid", collection="recipes")
    food_results = service.search("食品安全 鸡肉", mode="keyword", collection="food_safety")

    assert dense_collections == ["recipes"]
    assert {result.chunk.metadata["source"] for result in recipe_results} == {"recipes.md"}
    assert {result.chunk.metadata["source"] for result in food_results} == {"food.md"}


def test_ingest_recreate_and_hybrid_search_are_isolated_by_collection(tmp_path: Path):
    config = _config(tmp_path)
    food_path = tmp_path / "food_safety"
    recipe_path = tmp_path / "recipes"
    food_path.mkdir()
    recipe_path.mkdir()
    (food_path / "food.md").write_text("生鸡肉不建议清洗，应避免交叉污染。", encoding="utf-8")
    (recipe_path / "recipes.md").write_text("番茄意面：煮熟意面后加入番茄酱。", encoding="utf-8")

    food_config = with_collection(config, "food_safety")
    recipe_config = with_collection(config, "recipes")
    ingest_path(food_path, food_config, recreate=True)
    ingest_path(recipe_path, recipe_config, recreate=True)

    food_index = keyword_index_path(config.db_path, "food_safety")
    recipe_index = keyword_index_path(config.db_path, "recipes")
    recipe_index_before_recreate = recipe_index.read_text(encoding="utf-8")
    service = RetrievalService(config)

    food_dense = service.search("生鸡肉 清洗", mode="dense", collection="food_safety")
    recipe_hybrid = service.search("番茄意面", mode="hybrid", collection="recipes")

    assert food_index.exists()
    assert recipe_index.exists()
    assert {result.chunk.metadata["source"] for result in food_dense} == {"food.md"}
    assert {result.chunk.metadata["source"] for result in recipe_hybrid} == {"recipes.md"}

    (food_path / "food.md").write_text("新版食品安全资料：鸡肉必须彻底加热。", encoding="utf-8")
    ingest_path(food_path, food_config, recreate=True)

    recipe_after_food_recreate = service.search("番茄意面", mode="hybrid", collection="recipes")
    assert recipe_index.read_text(encoding="utf-8") == recipe_index_before_recreate
    assert {result.chunk.metadata["source"] for result in recipe_after_food_recreate} == {"recipes.md"}


def test_incremental_ingest_merges_keyword_index_with_existing_collection(tmp_path: Path):
    config = with_collection(_config(tmp_path), "food_safety")
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("生鸡肉不建议清洗。", encoding="utf-8")
    second.write_text("处理生鸡肉后要清洁台面。", encoding="utf-8")

    ingest_path(first, config, recreate=True)
    ingest_path(second, config, recreate=False)

    results = RetrievalService(config).search("生鸡肉 清洗", mode="keyword")

    assert {result.chunk.metadata["source"] for result in results} == {"first.md", "second.md"}
