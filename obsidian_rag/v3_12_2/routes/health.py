from fastapi import APIRouter

from obsidian_rag.v3_12_2.schemas import RerankHealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=RerankHealthResponse)
def health() -> RerankHealthResponse:
    return RerankHealthResponse(status="ok", version="v3.12.2", capability="retrieval-reranking")
