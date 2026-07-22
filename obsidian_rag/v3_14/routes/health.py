from fastapi import APIRouter, Depends

from obsidian_rag.v3_14.dependencies import get_learning_service
from obsidian_rag.v3_14.schemas import SandboxHealthResponse
from obsidian_rag.v3_14.service import SandboxLearningService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=SandboxHealthResponse)
def health(service: SandboxLearningService = Depends(get_learning_service)):
    sandbox = service.sandbox.runtime_status()
    mcp = service.manager.runtime()
    return SandboxHealthResponse(
        status="ok" if sandbox.available and mcp.started else "degraded",
        version="v3.14",
        sandbox_available=sandbox.available,
        docker_version=sandbox.docker_version,
        permission_policy_enabled=True,
        connected_mcp_servers=sum(item.status == "connected" for item in mcp.servers),
    )
