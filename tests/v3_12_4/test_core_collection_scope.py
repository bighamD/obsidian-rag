from pathlib import Path

from obsidian_rag.core.collections import CollectionScopeResolver, KnowledgeBaseRegistry, RetrievalScopeRequest


class FakeRouter:
    def route(self, question, candidates, max_collections, *, registry_path=None):
        from obsidian_rag.core.collections.schemas import RetrievalScope

        selected = candidates[:max_collections]
        return RetrievalScope(
            status="selected" if len(selected) == 1 else "multi_selected",
            selected_ids=[item.id for item in selected],
            selected_collections=[item.collection for item in selected],
            candidate_ids=[item.id for item in candidates],
            reason=f"测试路由：{question}",
            registry_path=registry_path,
        )


def test_resolver_honors_explicit_collection(tmp_path: Path):
    registry_path = tmp_path / "knowledge_bases.yaml"
    registry_path.write_text(
        "knowledge_bases:\n  - id: food\n    collection: food\n    description: food docs\n",
        encoding="utf-8",
    )
    registry = KnowledgeBaseRegistry(registry_path)
    resolver = CollectionScopeResolver(registry, FakeRouter(), default_collection="food")

    scope = resolver.resolve(
        RetrievalScopeRequest(
            question="生鸡肉要洗吗？",
            explicit_collection="food",
            router_enabled=True,
            max_collections=2,
        )
    )

    assert scope.status == "explicit"
    assert scope.selected_collections == ["food"]


def test_resolver_selects_multiple_collections(tmp_path: Path):
    registry_path = tmp_path / "knowledge_bases.yaml"
    registry_path.write_text(
        "knowledge_bases:\n"
        "  - id: food\n    collection: food\n    description: food docs\n"
        "  - id: recipes\n    collection: recipes\n    description: recipe docs\n",
        encoding="utf-8",
    )
    resolver = CollectionScopeResolver(
        KnowledgeBaseRegistry(registry_path),
        FakeRouter(),
        default_collection="food",
    )

    scope = resolver.resolve(
        RetrievalScopeRequest(
            question="鸡肉安全和做法",
            router_enabled=True,
            max_collections=2,
        )
    )

    assert scope.status == "multi_selected"
    assert scope.selected_collections == ["food", "recipes"]
