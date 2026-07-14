from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_11.dependencies import get_registry
from obsidian_rag.v3_11.schemas import (
    SkillDocument,
    SkillListResponse,
    SkillManifest,
    SkillRuntimeConfigResponse,
)
from obsidian_rag.v3_11.skills.registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillListResponse)
def list_skills(registry: SkillRegistry = Depends(get_registry)) -> SkillListResponse:
    return SkillListResponse(skills=registry.list_manifests(), errors=list(registry.errors))


@router.get("/config", response_model=SkillRuntimeConfigResponse)
def skill_runtime_config(registry: SkillRegistry = Depends(get_registry)) -> SkillRuntimeConfigResponse:
    return SkillRuntimeConfigResponse(
        skill_root=str(registry.root),
        candidate_count=len(registry.list_manifests()),
        router_mode="LLM JSON + invalid-selection/error fallback",
        run_store="InMemoryRunStore（复用 V3.10，进程重启后清空）",
    )


@router.get("/{skill_name}", response_model=SkillDocument | SkillManifest)
def get_skill(
    skill_name: str,
    include_content: bool = Query(default=True, description="是否返回 SKILL.md 正文；关闭时仅返回元数据。"),
    registry: SkillRegistry = Depends(get_registry),
) -> SkillDocument | SkillManifest:
    try:
        document = registry.load(skill_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if include_content:
        return document
    return SkillManifest(**document.model_dump(exclude={"content", "estimated_tokens"}))
