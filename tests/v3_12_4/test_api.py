from fastapi.testclient import TestClient

from obsidian_rag.core.collections.schemas import RetrievalScope
from obsidian_rag.v3_12_4.app import app
from obsidian_rag.v3_12_4.dependencies import get_integration_service
from obsidian_rag.v3_12_4.schemas import CollectionRouteDebugResponse, CollectionRuntimeResponse


class FakeService:
    def collection_runtime(self):
        return CollectionRuntimeResponse(
            registry_path="knowledge_bases.yaml",
            knowledge_bases=[],
            enabled_ids=[],
            errors=[],
        )

    def route_collection(self, request):
        return CollectionRouteDebugResponse(
            question=request.question,
            scope=RetrievalScope(status="no_collection", reason="测试没有匹配知识库。"),
        )


def test_collection_runtime_and_route_api():
    app.dependency_overrides[get_integration_service] = lambda: FakeService()
    with TestClient(app) as client:
        runtime = client.get("/collections/runtime")
        routed = client.post(
            "/collections/route",
            json={"question": "测试问题", "collection_router_enabled": True, "max_collections": 2},
        )
    app.dependency_overrides.clear()

    assert runtime.status_code == 200
    assert routed.status_code == 200
    assert routed.json()["scope"]["status"] == "no_collection"
