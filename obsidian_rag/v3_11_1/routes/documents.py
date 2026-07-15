from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from obsidian_rag.v3_11_1.dependencies import get_docling_service
from obsidian_rag.v3_11_1.schemas import (
    DoclingChunksResponse,
    DoclingConvertResponse,
    DoclingIngestRequest,
    DoclingIngestResponse,
    DoclingPathRequest,
    DoclingSearchRequest,
    DoclingSearchResponse,
)
from obsidian_rag.v3_11_1.service import DoclingLearningService


router = APIRouter(prefix="/documents", tags=["docling-documents"])


@router.post("/convert", response_model=DoclingConvertResponse)
def convert_document(
    request: DoclingPathRequest,
    service: DoclingLearningService = Depends(get_docling_service),
) -> DoclingConvertResponse:
    return _handle(lambda: service.convert(request))


@router.post("/chunks", response_model=DoclingChunksResponse)
def preview_chunks(
    request: DoclingPathRequest,
    service: DoclingLearningService = Depends(get_docling_service),
) -> DoclingChunksResponse:
    return _handle(lambda: service.chunks(request))


@router.post("/ingest", response_model=DoclingIngestResponse)
def ingest_documents(
    request: DoclingIngestRequest,
    service: DoclingLearningService = Depends(get_docling_service),
) -> DoclingIngestResponse:
    return _handle(lambda: service.ingest(request))


@router.post("/search", response_model=DoclingSearchResponse)
def search_documents(
    request: DoclingSearchRequest,
    service: DoclingLearningService = Depends(get_docling_service),
) -> DoclingSearchResponse:
    return _handle(lambda: service.search(request))


def _handle(call):
    try:
        return call()
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
