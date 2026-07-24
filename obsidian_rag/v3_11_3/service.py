from __future__ import annotations

from obsidian_rag.config import RagConfig
from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry
from obsidian_rag.v3_11_3.retrieval import MultiCollectionRetrievalService
from obsidian_rag.v3_11_3.router import CollectionRouter
from obsidian_rag.v3_11_3.schemas import (
    CollectionRouteRequest,
    CollectionRouteResponse,
    CollectionSearchRequest,
    CollectionSearchResponse,
    CollectionSelection,
    CollectionTraceEvent,
    KnowledgeBaseListResponse,
)


class CollectionRouterService:
    """V3.11.3 主编排：Registry -> Collection Router -> 多库 Retrieval -> RRF。"""

    def __init__(
        self,
        config: RagConfig,
        registry: KnowledgeBaseRegistry,
        retrieval_service,
        router: CollectionRouter | None = None,
    ):
        self.config = config
        self.registry = registry
        self.retrieval = MultiCollectionRetrievalService(retrieval_service)
        self.router = router or CollectionRouter()

    def list_collections(self) -> KnowledgeBaseListResponse:
        return KnowledgeBaseListResponse(
            registry_path=str(self.registry.path),
            knowledge_bases=self.registry.list_manifests(),
            errors=list(self.registry.errors),
        )

    def route(self, request: CollectionRouteRequest) -> CollectionRouteResponse:
        selection, trace = self._select(request)
        return CollectionRouteResponse(question=request.question, selection=selection, trace=trace)

    def search(self, request: CollectionSearchRequest) -> CollectionSearchResponse:
        selection, trace = self._select(request)
        if not selection.selected_collections:
            return CollectionSearchResponse(
                query=request.question,
                mode=request.mode,
                selection=selection,
                collection_result_counts={},
                collection_errors={},
                results=[],
                trace=trace,
            )

        results, counts, errors = self.retrieval.search(
            request.question,
            selection.selected_collections,
            top_k=request.top_k,
            mode=request.mode,
        )
        trace.append(
            CollectionTraceEvent(
                node_name="retrieve_collections",
                event_type="retrieved",
                reason=f"已完成 {len(selection.selected_collections)} 个 collection 的 {request.mode} 检索。",
                metadata={"result_counts": counts, "errors": errors},
            )
        )
        trace.append(
            CollectionTraceEvent(
                node_name="cross_collection_rrf",
                event_type="fused",
                reason=f"第二层 RRF 返回 {len(results)} 条全局结果。",
                metadata={"top_k": request.top_k},
            )
        )
        debug_breakpoint(
            "v3_11_3.search.completed",
            collections=selection.selected_collections,
            result_counts=counts,
            errors=errors,
            fused_count=len(results),
        )
        return CollectionSearchResponse(
            query=request.question,
            mode=request.mode,
            selection=selection,
            collection_result_counts=counts,
            collection_errors=errors,
            results=results,
            trace=trace,
        )

    def _select(self, request: CollectionRouteRequest) -> tuple[CollectionSelection, list[CollectionTraceEvent]]:
        candidates = self.registry.list_manifests(enabled_only=True)
        candidate_ids = [candidate.id for candidate in candidates]
        trace = [
            CollectionTraceEvent(
                node_name="load_registry",
                event_type="candidates",
                reason=f"Registry 提供 {len(candidates)} 个启用知识库。",
                metadata={"candidate_ids": candidate_ids, "errors": list(self.registry.errors)},
            )
        ]
        debug_breakpoint(
            "v3_11_3.registry.loaded",
            registry_path=self.registry.path,
            candidates=candidates,
            errors=self.registry.errors,
        )

        if request.collection:
            manifest = self.registry.get_by_collection(request.collection)
            if manifest is None:
                selection = CollectionSelection(
                    status="invalid_selection",
                    reason=f"显式 collection {request.collection} 未在启用 Registry 中登记。",
                    candidate_ids=candidate_ids,
                )
            else:
                selection = CollectionSelection(
                    status="explicit",
                    selected_ids=[manifest.id],
                    selected_collections=[manifest.collection],
                    reason="请求显式指定 collection，跳过 LLM Router。",
                    candidate_ids=candidate_ids,
                )
        elif not request.router_enabled:
            manifest = self.registry.get_by_collection(self.config.collection_name)
            if manifest is None:
                selection = CollectionSelection(
                    status="invalid_selection",
                    reason=f"Router 已关闭，但默认 collection {self.config.collection_name} 未在启用 Registry 中登记。",
                    candidate_ids=candidate_ids,
                )
            else:
                selection = CollectionSelection(
                    status="disabled",
                    selected_ids=[manifest.id],
                    selected_collections=[manifest.collection],
                    reason="Collection Router 已关闭，使用 RAG_COLLECTION 默认知识库。",
                    candidate_ids=candidate_ids,
                )
        else:
            selection = self.router.route(request.question, candidates, request.max_collections)

        trace.append(
            CollectionTraceEvent(
                node_name="collection_router",
                event_type=selection.status,
                reason=selection.reason,
                metadata={
                    "selected_ids": selection.selected_ids,
                    "selected_collections": selection.selected_collections,
                    "confidence": selection.confidence,
                },
            )
        )
        debug_breakpoint("v3_11_3.router.selected", selection=selection)
        return selection, trace
