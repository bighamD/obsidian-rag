from pathlib import Path

from obsidian_rag.core.collections.schemas import RetrievalScope
from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.permissions import PermissionPrincipal, StaticPermissionPolicy
from obsidian_rag.core.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult
from obsidian_rag.v3_13.agent import PermissionAwareAgentService
from obsidian_rag.v3_13.schemas import PermissionAskRequest


class FakePlanner:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="检索菜谱",
                steps=[
                    PlanStep(id="s1", kind="search", query="番茄炒鸡蛋"),
                    PlanStep(id="s2", kind="synthesize", instruction="综合回答"),
                ],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeResolver:
    def resolve(self, request):
        return RetrievalScope(
            status="selected",
            selected_ids=["recipes"],
            selected_collections=["recipes"],
            reason="菜谱问题。",
        )


class FakeRetrieval:
    def collection_name(self, collection=None):
        return collection or "recipes"


class FakeChat:
    def complete(self, messages):
        return "当前主体没有知识库读取权限。"


def test_restricted_principal_is_blocked_before_search(tmp_path: Path):
    called = False
    registry = ToolRegistry()

    def search_notes(**kwargs):
        nonlocal called
        called = True
        return ToolResult(tool_name="search_notes", status="success")

    registry.register(
        "search_notes",
        search_notes,
        ToolDefinition(
            name="search_notes",
            read_only=True,
            risk_level="safe",
            required_permission="knowledge.read",
        ),
    )
    service = PermissionAwareAgentService(
        retrieval_service=FakeRetrieval(),
        retrieval_scope_resolver=FakeResolver(),
        permission_policy=StaticPermissionPolicy(),
        planner_service=FakePlanner(),
        chat_client=FakeChat(),
        tool_registry=registry,
        planner_tools=[],
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )

    response = service.ask(
        PermissionAskRequest(
            question="番茄炒鸡蛋怎么做？",
            memory_compaction_enabled=False,
            max_retries=0,
            principal=PermissionPrincipal(
                roles=["restricted"],
                permissions=[],
                tool_allowlist=[],
                allowed_collections=[],
            ),
        )
    )

    assert "authorize_steps" in response.graph_path
    assert response.permission_report is not None
    assert response.permission_report.decisions[0].decision == "deny"
    assert response.step_results[0].status == "failed"
    assert called is False
