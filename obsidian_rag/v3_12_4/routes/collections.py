from fastapi import APIRouter, Depends

from obsidian_rag.v3_12_4.dependencies import get_integration_service
from obsidian_rag.v3_12_4.schemas import (
    CollectionRouteDebugRequest,
    CollectionRouteDebugResponse,
    CollectionRuntimeResponse,
)
from obsidian_rag.v3_12_4.service import UnifiedKnowledgeRoutingService


router = APIRouter(prefix="/collections", tags=["collection-routing"])


@router.get("/runtime", response_model=CollectionRuntimeResponse)
def runtime(
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> CollectionRuntimeResponse:
    return service.collection_runtime()


@router.post("/route", response_model=CollectionRouteDebugResponse)
def route(
    request: CollectionRouteDebugRequest,
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> CollectionRouteDebugResponse:
    return service.route_collection(request)
