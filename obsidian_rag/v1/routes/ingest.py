from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from obsidian_rag.config import RagConfig, resolve_ingest_path
from obsidian_rag.pipeline import ingest_path
from obsidian_rag.v1.dependencies import get_config
from obsidian_rag.v1.schemas import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    config: RagConfig = Depends(get_config),
) -> IngestResponse:
    path = resolve_ingest_path(Path(request.path).expanduser() if request.path else None, config)
    document_count, chunk_count = ingest_path(path, config=config, recreate=request.recreate)
    return IngestResponse(document_count=document_count, chunk_count=chunk_count)
