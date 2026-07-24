from fastapi import APIRouter, Depends

from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import PermissionHealthResponse
from obsidian_rag.v3_13.service import PermissionLearningService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=PermissionHealthResponse)
def health(
    service: PermissionLearningService = Depends(get_learning_service),
) -> PermissionHealthResponse:
    runtime = service.manager.runtime()
    manifests = service.registry.list_manifests(enabled_only=True)
    connected = sum(server.status == "connected" for server in runtime.servers)
    expected = len([server for server in runtime.servers])
    return PermissionHealthResponse(
        status="ok" if runtime.started and connected == expected else "degraded",
        version="v3.13",
        permission_policy_enabled=True,
        mcp_started=runtime.started,
        connected_mcp_servers=connected,
        enabled_knowledge_bases=len(manifests),
    )
