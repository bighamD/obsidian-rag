from fastapi import FastAPI
from fastapi.testclient import TestClient

from obsidian_rag.core.permissions import PermissionPrincipal, PermissionReport
from obsidian_rag.v3_15.dependencies import get_learning_service
from obsidian_rag.v3_15.routes import approvals
from obsidian_rag.v3_15.schemas import ApprovalListResponse, ApprovalRecord, ApprovalRequest


class FakeService:
    def __init__(self):
        request = ApprovalRequest(
            approval_id="approval_run_test",
            run_id="run_test",
            conversation_id="conv_test",
            summary="需要确认。",
            steps=[],
            permission_report=PermissionReport(
                principal=PermissionPrincipal(),
                decisions=[],
                allow_count=0,
                confirm_count=0,
                deny_count=0,
                all_allowed=True,
                summary="测试。",
            ),
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.record = ApprovalRecord(request=request, status="pending")

    def approval(self, run_id):
        return self.record if run_id == "run_test" else None

    def approvals(self, status, limit):
        return ApprovalListResponse(approvals=[self.record])


def test_approval_query_api():
    app = FastAPI()
    app.include_router(approvals.router)
    app.dependency_overrides[get_learning_service] = lambda: FakeService()

    with TestClient(app) as client:
        response = client.get("/approvals/run_test")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
