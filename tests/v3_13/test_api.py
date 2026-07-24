from fastapi.testclient import TestClient

from obsidian_rag.core.permissions import PermissionPrincipal, PermissionReport
from obsidian_rag.v3_13.app import app
from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import (
    PermissionAuditListResponse,
    PermissionEvaluateResponse,
    SkillRouteDebugResponse,
    SkillRuntimeResponse,
)
from obsidian_rag.core.skills.schemas import SkillManifest, SkillSelection


class FakeService:
    def evaluate(self, request):
        return PermissionEvaluateResponse(
            report=PermissionReport(
                principal=request.principal,
                decisions=[],
                allow_count=0,
                confirm_count=0,
                deny_count=0,
                all_allowed=True,
                summary="测试通过。",
            )
        )

    def audit(self, limit):
        return PermissionAuditListResponse(persistence="in_memory", records=[])

    def skill_runtime(self):
        return SkillRuntimeResponse(
            root="/tmp/skills",
            skills=[SkillManifest(name="food-safety", description="食品安全", path="food/SKILL.md")],
            errors=[],
        )

    def route_skill(self, request):
        return SkillRouteDebugResponse(
            question=request.question,
            selection=SkillSelection(
                status="selected",
                selected_skill="food-safety",
                reason="测试选择。",
                candidate_names=["food-safety"],
            ),
        )


def test_permission_evaluate_and_audit_api():
    app.dependency_overrides[get_learning_service] = lambda: FakeService()
    with TestClient(app) as client:
        evaluated = client.post(
            "/permissions/evaluate",
            json={
                "principal": PermissionPrincipal().model_dump(),
                "action": {"kind": "tool", "tool_name": "demo::get_server_time", "arguments": {}},
            },
        )
        audited = client.get("/permissions/audit")
    app.dependency_overrides.clear()

    assert evaluated.status_code == 200
    assert audited.status_code == 200
    assert evaluated.json()["report"]["all_allowed"] is True


def test_skill_runtime_and_route_api():
    app.dependency_overrides[get_learning_service] = lambda: FakeService()
    with TestClient(app) as client:
        runtime = client.get("/skills/runtime")
        routed = client.post("/skills/route", json={"question": "生鸡肉要不要洗？"})
    app.dependency_overrides.clear()

    assert runtime.status_code == 200
    assert routed.status_code == 200
    assert routed.json()["selection"]["selected_skill"] == "food-safety"
