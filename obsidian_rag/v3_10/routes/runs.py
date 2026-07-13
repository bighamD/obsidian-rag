from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_10.dependencies import get_run_store, get_runtime_config
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import RunRecord, RuntimeConfigResponse


router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunRecord])
def list_runs(
    limit: int = Query(default=20, ge=1, le=100, description="最多返回多少条最近 Run。"),
    run_store: InMemoryRunStore = Depends(get_run_store),
) -> list[RunRecord]:
    return run_store.list_recent(limit)


@router.get("/runs/{run_id}", response_model=RunRecord)
def get_run(
    run_id: str,
    run_store: InMemoryRunStore = Depends(get_run_store),
) -> RunRecord:
    record = run_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return record


@router.get("/runtime/config", response_model=RuntimeConfigResponse)
def runtime_config(config: RuntimeConfigResponse = Depends(get_runtime_config)) -> RuntimeConfigResponse:
    return config
