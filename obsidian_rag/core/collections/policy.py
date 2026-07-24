from __future__ import annotations

from typing import Any

from obsidian_rag.core.collections.registry import KnowledgeBaseRegistry
from obsidian_rag.core.collections.schemas import KnowledgeBaseManifest, RetrievalScope


class SearchCollectionPolicy:
    """将 Planner 选择确定性地规范为可执行的物理 Collections。"""

    def __init__(
        self,
        registry: KnowledgeBaseRegistry,
        default_collection: str,
        max_collections: int = 3,
    ):
        self.registry = registry
        self.default_collection = default_collection
        self.max_collections = max_collections

    def list_manifests(self) -> list[KnowledgeBaseManifest]:
        return self.registry.list_manifests(enabled_only=True)

    def resolve(
        self,
        *,
        planner_collections: Any,
        explicit_collection: str | None = None,
    ) -> RetrievalScope:
        manifests = self.list_manifests()
        candidate_ids = [item.id for item in manifests]
        registry_path = str(self.registry.path)

        if not explicit_collection and planner_collections is not None and (
            not isinstance(planner_collections, list)
            or any(not isinstance(item, str) for item in planner_collections)
        ):
            return RetrievalScope(
                status="invalid_selection",
                reason="Planner 的 arguments.collections 必须是字符串数组。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors={"collections": "必须是字符串数组"},
            )

        if explicit_collection:
            requested = [explicit_collection]
            status = "explicit"
            reason = "请求显式指定 Collection，覆盖 Planner 选择。"
        elif planner_collections is None:
            requested = [self.default_collection]
            status = "selected"
            reason = "Planner 未提供 Collection，使用默认知识库兼容路径。"
        else:
            requested = _stable_unique(planner_collections)
            status = "selected" if len(requested) == 1 else "multi_selected"
            reason = "使用 Planner 在 search step 中选择的知识库范围。"

        if not requested:
            return RetrievalScope(
                status="no_collection",
                reason="Planner 明确返回空 Collection，本步骤不执行知识库检索。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
            )
        if len(requested) > self.max_collections:
            return RetrievalScope(
                status="invalid_selection",
                reason=f"Planner 选择了 {len(requested)} 个知识库，超过上限 {self.max_collections}。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors={"collections": "超过最大 Collection 数量"},
            )

        by_name: dict[str, KnowledgeBaseManifest | None] = {
            alias: manifest
            for manifest in manifests
            for alias in (manifest.id, manifest.collection)
        }
        by_name.setdefault(self.default_collection, None)
        unknown = [name for name in requested if name not in by_name]
        if unknown:
            return RetrievalScope(
                status="invalid_selection",
                reason=f"Planner 选择了未知知识库：{', '.join(unknown)}。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors={"unknown_collections": ", ".join(unknown)},
            )

        selected = [by_name[name] for name in requested]
        selected_ids = _stable_unique([item.id for item in selected if item is not None])
        selected_collections = _stable_unique(
            [item.collection if item is not None else name for name, item in zip(requested, selected, strict=True)]
        )
        return RetrievalScope(
            status=status,
            selected_ids=selected_ids,
            selected_collections=selected_collections,
            candidate_ids=candidate_ids,
            reason=reason,
            registry_path=registry_path,
        )


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
