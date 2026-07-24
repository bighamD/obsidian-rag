from __future__ import annotations

from obsidian_rag.core.collections.registry import KnowledgeBaseRegistry
from obsidian_rag.core.collections.router import LlmCollectionRouter
from obsidian_rag.core.collections.schemas import RetrievalScope, RetrievalScopeRequest


class CollectionScopeResolver:
    """按照显式 Collection、Router 和默认 Collection 的优先级解析范围。"""

    def __init__(
        self,
        registry: KnowledgeBaseRegistry,
        router: LlmCollectionRouter,
        default_collection: str,
    ):
        self.registry = registry
        self.router = router
        self.default_collection = default_collection

    def resolve(self, request: RetrievalScopeRequest) -> RetrievalScope:
        candidates = self.registry.list_manifests(enabled_only=True)
        candidate_ids = [item.id for item in candidates]
        registry_path = str(self.registry.path)
        registry_errors = {f"registry_{index}": value for index, value in enumerate(self.registry.errors, start=1)}

        if request.explicit_collection:
            manifest = self.registry.get_by_collection(request.explicit_collection)
            if manifest is None:
                return RetrievalScope(
                    status="invalid_selection",
                    reason=f"显式 Collection {request.explicit_collection} 未在启用 Registry 中登记。",
                    candidate_ids=candidate_ids,
                    registry_path=registry_path,
                    errors=registry_errors,
                )
            return RetrievalScope(
                status="explicit",
                selected_ids=[manifest.id],
                selected_collections=[manifest.collection],
                reason="请求显式指定 Collection，跳过 LLM Router。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors=registry_errors,
            )

        if not request.router_enabled:
            manifest = self.registry.get_by_collection(self.default_collection)
            if manifest is None:
                return RetrievalScope(
                    status="invalid_selection",
                    reason=f"Router 已关闭，但默认 Collection {self.default_collection} 未在 Registry 中登记。",
                    candidate_ids=candidate_ids,
                    registry_path=registry_path,
                    errors=registry_errors,
                )
            return RetrievalScope(
                status="disabled",
                selected_ids=[manifest.id],
                selected_collections=[manifest.collection],
                reason="Collection Router 已关闭，使用默认知识库。",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors=registry_errors,
            )

        scope = self.router.route(
            request.question,
            candidates,
            request.max_collections,
            registry_path=registry_path,
        )
        return scope.model_copy(update={"errors": {**registry_errors, **scope.errors}})
