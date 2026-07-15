from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_11.agent.service import SkillAgentService
from obsidian_rag.v3_11.schemas import SkillAskRequest


class FakeRegistry:
    def list_manifests(self):
        return []


class FakePlanner:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(goal="回答菜谱问题", steps=[PlanStep(id="s1", kind="search", query="番茄意面")]),
            graph_path=[],
            trace=[],
        )


class CapturingRetrievalService:
    def __init__(self):
        self.collections = []

    def search(self, query, top_k=5, mode="hybrid", filters=None, collection=None):
        self.collections.append(collection)
        return [
            SearchResult(
                chunk=TextChunk(text="番茄意面菜谱。", metadata={"source": "recipes.md", "chunk_id": "RC-001"}),
                score=0.9,
            )
        ]

    def collection_name(self, collection=None):
        return collection or "obsidian_notes"


class FakeChatClient:
    def complete(self, messages):
        return "先煮意面，再加入番茄酱。"


def test_skill_agent_propagates_collection_to_base_agent(tmp_path):
    retrieval = CapturingRetrievalService()
    service = SkillAgentService(
        retrieval_service=retrieval,
        registry=FakeRegistry(),
        planner_service=FakePlanner(),
        chat_client=FakeChatClient(),
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )

    response = service.ask(
        SkillAskRequest(question="番茄意面怎么做？", collection="recipes", skill_router_enabled=False)
    )

    assert retrieval.collections == ["recipes"]
    assert response.agent_response.collection == "recipes"
