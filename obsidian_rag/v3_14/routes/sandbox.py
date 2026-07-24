from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from obsidian_rag.v3_14.dependencies import get_learning_service
from obsidian_rag.v3_14.schemas import SandboxArtifactListResponse, SandboxCallRequest, SandboxCallResponse, SandboxRuntimeConfigResponse
from obsidian_rag.v3_14.service import SandboxLearningService


router = APIRouter(prefix="/sandbox", tags=["sandbox-execution"])


@router.get("/runtime", response_model=SandboxRuntimeConfigResponse)
def runtime(service: SandboxLearningService = Depends(get_learning_service)):
    return service.runtime_config()


@router.post("/call", response_model=SandboxCallResponse)
def call(request: SandboxCallRequest, service: SandboxLearningService = Depends(get_learning_service)):
    return service.sandbox_call(request)


@router.get("/artifacts/{run_id}", response_model=SandboxArtifactListResponse)
def artifacts(run_id: str, service: SandboxLearningService = Depends(get_learning_service)):
    return service.artifacts(run_id)


@router.get("/artifacts/{run_id}/{artifact_id}", response_class=FileResponse)
def download(run_id: str, artifact_id: str, service: SandboxLearningService = Depends(get_learning_service)):
    try:
        record, path = service.sandbox.artifact_path(run_id, artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=record.mime_type, filename=path.name)
