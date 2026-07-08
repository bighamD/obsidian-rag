from __future__ import annotations

from fastapi import APIRouter, Depends

from obsidian_rag.v3.agent.service import AgentService
from obsidian_rag.v3.dependencies import get_agent_service
from obsidian_rag.v3.schemas import AgentAskRequest, AgentAskResponse

router = APIRouter()


@router.post("/agent/ask", response_model=AgentAskResponse)
def agent_ask(
    request: AgentAskRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentAskResponse:
    return agent_service.ask(request)
