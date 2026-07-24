from pathlib import Path

from obsidian_rag.schema import TextChunk
from obsidian_rag.v1.retrieval.keyword import KeywordIndex, keyword_index_path


def test_keyword_index_finds_exact_chunk_id_and_chinese_terms(tmp_path: Path):
    index_path = tmp_path / "keyword_index.json"
    index = KeywordIndex(index_path)
    chunks = [
        TextChunk(
            text="不建议清洗生鸡肉，水花可能造成交叉污染。",
            metadata={"source": "food.md", "chunk_id": "KB-072", "topic": "不建议清洗生鸡肉"},
        ),
        TextChunk(
            text="鸡肉和禽肉需要加热到 74°C。",
            metadata={"source": "temp.md", "chunk_id": "KB-044", "topic": "禽肉安全温度"},
        ),
    ]

    index.build(chunks)
    index.save()

    loaded = KeywordIndex(index_path)
    loaded.load()
    results = loaded.search("KB-072 生鸡肉 清洗", top_k=2)

    assert results[0].chunk.metadata["chunk_id"] == "KB-072"
    assert results[0].score > results[1].score


def test_keyword_index_returns_empty_results_when_file_is_missing(tmp_path: Path):
    index = KeywordIndex(tmp_path / "missing.json")

    assert index.search("anything", top_k=5) == []


def test_keyword_index_paths_are_isolated_by_collection(tmp_path: Path):
    db_path = tmp_path / "qdrant"

    food_path = keyword_index_path(db_path, "food_safety")
    recipe_path = keyword_index_path(db_path, "recipes")

    assert food_path == tmp_path / "keyword_indexes" / "food_safety.json"
    assert recipe_path == tmp_path / "keyword_indexes" / "recipes.json"
    assert food_path != recipe_path
