from pathlib import Path

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry
from obsidian_rag.v3_11_3.retrieval import MultiCollectionRetrievalService
from obsidian_rag.v3_11_3.router import CollectionRouter
from obsidian_rag.v3_11_3.schemas import KnowledgeBaseManifest


def test_registry_skips_duplicate_and_disabled_entries(tmp_path: Path):
    path = tmp_path / "knowledge_bases.yaml"
    path.write_text(
        """knowledge_bases:
  - id: recipes
    collection: recipes
    description: 菜谱
    enabled: true
  - id: recipes_copy
    collection: recipes
    description: 重复物理库
    enabled: true
  - id: archived
    collection: archived
    description: 已停用
    enabled: false
""",
        encoding="utf-8",
    )
    registry = KnowledgeBaseRegistry(path)

    manifests = registry.load()

    assert [item.id for item in manifests] == ["recipes", "archived"]
    assert [item.id for item in registry.list_manifests(enabled_only=True)] == ["recipes"]
    assert "重复 collection" in registry.errors[0]


class FakeChatClient:
    def __init__(self, output: str):
        self.output = output
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.output


def _candidates() -> list[KnowledgeBaseManifest]:
    return [
        KnowledgeBaseManifest(id="food_safety", collection="food_safety", description="食品安全"),
        KnowledgeBaseManifest(id="recipes", collection="recipes", description="菜谱"),
    ]


def test_router_selects_two_registered_collections():
    chat = FakeChatClient(
        '{"knowledge_base_ids":["recipes","food_safety"],"reason":"跨领域问题","confidence":0.9}'
    )

    selection = CollectionRouter(chat_client=chat).route("鸡肉怎么做更安全？", _candidates(), 2)

    assert selection.status == "multi_selected"
    assert selection.selected_collections == ["recipes", "food_safety"]


def test_router_rejects_unknown_and_unparseable_selection():
    unknown = CollectionRouter(
        chat_client=FakeChatClient('{"knowledge_base_ids":["unknown"],"reason":"错误","confidence":0.2}')
    ).route("问题", _candidates(), 2)
    broken = CollectionRouter(chat_client=FakeChatClient("not-json")).route("问题", _candidates(), 2)

    assert unknown.status == "invalid_selection"
    assert broken.status == "router_error"


def test_router_handles_no_collection_and_too_many_selections():
    no_collection = CollectionRouter(
        chat_client=FakeChatClient('{"knowledge_base_ids":[],"reason":"无适用知识库","confidence":0.8}')
    ).route("天气如何", _candidates(), 2)
    too_many = CollectionRouter(
        chat_client=FakeChatClient(
            '{"knowledge_base_ids":["recipes","food_safety"],"reason":"越界","confidence":0.2}'
        )
    ).route("问题", _candidates(), 1)

    assert no_collection.status == "no_collection"
    assert no_collection.selected_collections == []
    assert too_many.status == "invalid_selection"
    assert "超过上限 1" in too_many.reason


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", collection=None):
        if collection == "broken":
            raise RuntimeError("collection unavailable")
        return [
            SearchResult(
                chunk=TextChunk(
                    text=f"{collection} result",
                    metadata={"source": f"{collection}.md", "chunk_id": "SHARED-001"},
                ),
                score=0.8,
            )
        ]


def test_multi_collection_rrf_keeps_same_chunk_id_separate_and_preserves_partial_success():
    service = MultiCollectionRetrievalService(FakeRetrievalService())

    results, counts, errors = service.search(
        "鸡肉",
        ["recipes", "food_safety", "broken"],
        top_k=5,
        mode="hybrid",
    )

    assert {item.collection for item in results} == {"recipes", "food_safety"}
    assert all(item.chunk_id == "SHARED-001" for item in results)
    assert counts == {"recipes": 1, "food_safety": 1}
    assert errors == {"broken": "collection unavailable"}
