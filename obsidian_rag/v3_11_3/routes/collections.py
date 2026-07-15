from __future__ import annotations

from fastapi import APIRouter, Depends

from obsidian_rag.v3_11_3.dependencies import get_collection_router_service
from obsidian_rag.v3_11_3.schemas import (
    CollectionRouteRequest,
    CollectionRouteResponse,
    CollectionSearchRequest,
    CollectionSearchResponse,
    KnowledgeBaseListResponse,
)
from obsidian_rag.v3_11_3.service import CollectionRouterService


router = APIRouter(prefix="/collections", tags=["collection-router"])


@router.get("", response_model=KnowledgeBaseListResponse)
def list_collections(
    service: CollectionRouterService = Depends(get_collection_router_service),
) -> KnowledgeBaseListResponse:
    return service.list_collections()


@router.post("/route", response_model=CollectionRouteResponse)
def route_collection(
    request: CollectionRouteRequest,
    service: CollectionRouterService = Depends(get_collection_router_service),
) -> CollectionRouteResponse:
    return service.route(request)


@router.post("/search", response_model=CollectionSearchResponse)
def search_collections(
    request: CollectionSearchRequest,
    service: CollectionRouterService = Depends(get_collection_router_service),
) -> CollectionSearchResponse:
    return service.search(request)
