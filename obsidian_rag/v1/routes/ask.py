from __future__ import annotations

from fastapi import APIRouter, Depends

from obsidian_rag.v1.dependencies import get_answer_service
from obsidian_rag.v1.schemas import AskRequest, AskResponse, to_search_hit
from obsidian_rag.v1.services.answer_service import AnswerService

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    answer_service: AnswerService = Depends(get_answer_service),
) -> AskResponse:
    answer, results = answer_service.answer(request)
    return AskResponse(
        question=request.question,
        answer=answer,
        results=[to_search_hit(result) for result in results],
        sources=answer_service.sources(results),
    )
