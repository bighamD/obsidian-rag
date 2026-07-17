from pathlib import Path

from obsidian_rag.core.collections.schemas import RetrievalScope
from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_12_4.agent import RoutedMcpAgentService
from obsidian_rag.v3_12_4.schemas import RoutedMcpAskRequest


class FakePlanner:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="跨库检索",
                steps=[
                    PlanStep(id="s1", kind="search", query="鸡肉安全和做法"),
                    PlanStep(id="s2", kind="synthesize", instruction="综合回答", depends_on=["s1"]),
                ],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeResolver:
    def resolve(self, request):
        return RetrievalScope(
            status="multi_selected",
            selected_ids=["food", "recipes"],
            selected_collections=["food_safety", "recipes"],
            candidate_ids=["food", "recipes"],
            reason="问题同时涉及安全和做法。",
        )


class FakeRetrieval:
    def collection_name(self, collection=None):
        return collection or "food_safety"


class FakeChat:
    def complete(self, messages):
        return "不要清洗生鸡肉，并按菜谱充分加热。"


def test_agent_routes_then_searches_multiple_collections(tmp_path: Path):
    registry = ToolRegistry()

    def search_notes(query, top_k, mode, filters=None, collection=None, collections=None):
        assert collections == ["food_safety", "recipes"]
        results = [
            SearchResult(
                chunk=TextChunk(
                    text="不要冲洗生鸡肉。",
                    metadata={"source": "food.md", "chunk_id": "KB-072", "collection": "food_safety"},
                ),
                score=0.9,
            )
        ]
        return ToolResult(
            tool_name="search_notes",
            status="success",
            results=results,
            metadata={"collections": collections, "collection_errors": {}},
        )

    registry.register("search_notes", search_notes, ToolDefinition(name="search_notes", read_only=True))
    service = RoutedMcpAgentService(
        retrieval_service=FakeRetrieval(),
        retrieval_scope_resolver=FakeResolver(),
        planner_service=FakePlanner(),
        chat_client=FakeChat(),
        tool_registry=registry,
        planner_tools=[],
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )

    response = service.ask(
        RoutedMcpAskRequest(
            question="做鸡肉时怎样保证安全，同时给我一个简单做法？",
            memory_compaction_enabled=False,
        )
    )

    assert response.graph_path[3] == "resolve_retrieval_scope"
    assert response.retrieval_scope is not None
    assert response.retrieval_scope.selected_collections == ["food_safety", "recipes"]
    assert response.step_results[0].metadata["collections"] == ["food_safety", "recipes"]
    assert response.collection == "food_safety,recipes"
