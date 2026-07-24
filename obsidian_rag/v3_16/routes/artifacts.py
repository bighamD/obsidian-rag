from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.schemas import DeepAgentArtifactListResponse
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(prefix="/artifacts", tags=["deepagents-artifacts"])


@router.get("/runs/{run_id}", response_model=DeepAgentArtifactListResponse)
def list_artifacts(
    run_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    return service.artifacts(run_id)


@router.get("/{artifact_id}/download", response_class=FileResponse)
def download_artifact(
    artifact_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    try:
        record, path = service.artifact_path(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=record.mime_type, filename=path.name)

