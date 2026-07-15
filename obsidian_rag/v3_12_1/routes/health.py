from fastapi import APIRouter

from obsidian_rag.v3_12_1.schemas import CoreHealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=CoreHealthResponse)
def health() -> CoreHealthResponse:
    return CoreHealthResponse(status="ok", version="v3.12.1", core_package="obsidian_rag.core")
