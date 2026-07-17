from fastapi import APIRouter, Depends

from obsidian_rag.v3_12_2.dependencies import get_learning_service
from obsidian_rag.v3_12_2.schemas import RerankEvalRequest, RerankEvalResponse, RerankSearchRequest, RerankSearchResponse
from obsidian_rag.v3_12_2.service import RerankerLearningService


router = APIRouter(prefix="/rerank", tags=["retrieval-reranking"])


@router.post("/search", response_model=RerankSearchResponse)
def search(request: RerankSearchRequest, service: RerankerLearningService = Depends(get_learning_service)):
    return service.search(request)


@router.post("/evaluate", response_model=RerankEvalResponse)
def evaluate(request: RerankEvalRequest, service: RerankerLearningService = Depends(get_learning_service)):
    return service.evaluate(request)
