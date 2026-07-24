from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from obsidian_rag.v3_14.schemas import SandboxArtifactListResponse, SandboxRuntimeConfigResponse
from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(prefix="/sandbox", tags=["deepagents-sandbox-backend"])


@router.get("/runtime", response_model=SandboxRuntimeConfigResponse)
def runtime(service: DeepAgentLearningService = Depends(get_learning_service)):
    return SandboxRuntimeConfigResponse(
        version="v3.16",
        json_endpoint="/agent/ask",
        stream_endpoint="/agent/ask/stream",
        sandbox_call_endpoint="",
        artifacts_endpoint="/sandbox/artifacts/{run_id}",
        sandbox=service.sandbox.runtime_status(),
        permission_policy_enabled=False,
        skill_router_enabled=False,
        approval_resume_enabled=True,
    )


@router.get("/artifacts/{run_id}", response_model=SandboxArtifactListResponse)
def artifacts(
    run_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    projected = service.artifacts(run_id)
    return SandboxArtifactListResponse(run_id=run_id, artifacts=projected.artifacts)


@router.get("/artifacts/{run_id}/{artifact_id}", response_class=FileResponse)
def download(
    run_id: str,
    artifact_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    try:
        record, path = service.sandbox.artifact_path(run_id, artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=record.mime_type, filename=path.name)

