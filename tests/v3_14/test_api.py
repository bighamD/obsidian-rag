from fastapi.testclient import TestClient

from obsidian_rag.core.permissions import PermissionPrincipal, PermissionReport
from obsidian_rag.core.sandbox import SandboxProfile, SandboxRuntimeStatus
from obsidian_rag.v3_14.app import app
from obsidian_rag.v3_14.dependencies import get_learning_service
from obsidian_rag.v3_14.schemas import SandboxArtifactListResponse, SandboxCallResponse, SandboxRuntimeConfigResponse


class FakeService:
    def runtime_config(self):
        return SandboxRuntimeConfigResponse(
            version="v3.14",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            sandbox_call_endpoint="/sandbox/call",
            artifacts_endpoint="/sandbox/artifacts/{run_id}",
            sandbox=SandboxRuntimeStatus(
                backend="docker",
                available=True,
                docker_version="test",
                workspace_root="/tmp/sandbox",
                profile=SandboxProfile(),
            ),
            permission_policy_enabled=True,
            skill_router_enabled=True,
            approval_resume_enabled=False,
        )

    def sandbox_call(self, request):
        return SandboxCallResponse(
            permission=PermissionReport(
                principal=request.principal,
                decisions=[],
                allow_count=1,
                confirm_count=0,
                deny_count=0,
                all_allowed=True,
                summary="允许。",
            ),
            executed=True,
            status="success",
            data={"path": "result.txt"},
        )

    def artifacts(self, run_id):
        return SandboxArtifactListResponse(run_id=run_id, artifacts=[])


def test_sandbox_runtime_call_and_artifacts_api():
    app.dependency_overrides[get_learning_service] = lambda: FakeService()
    with TestClient(app) as client:
        runtime = client.get("/sandbox/runtime")
        called = client.post(
            "/sandbox/call",
            json={
                "run_id": "run_test",
                "name": "sandbox::list_files",
                "arguments": {},
                "principal": PermissionPrincipal().model_dump(),
            },
        )
        artifacts = client.get("/sandbox/artifacts/run_test")
    app.dependency_overrides.clear()

    assert runtime.status_code == 200
    assert called.status_code == 200
    assert artifacts.status_code == 200
