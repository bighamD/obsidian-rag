from pathlib import Path

from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.core.skills.schemas import SkillDocument, SkillManifest, SkillSelection
from obsidian_rag.v3_13.agent import PermissionAwareAgentService
from obsidian_rag.v3_13.schemas import PermissionAskRequest


class FakeSkillResolver:
    root = "/tmp/skills"
    errors = []

    def list_manifests(self):
        return [
            SkillManifest(
                name="food-safety",
                description="食品安全问题处理方法。",
                triggers=["鸡肉", "温度"],
                path="food-safety/SKILL.md",
            )
        ]

    def select(
        self,
        *,
        question,
        candidates,
        skill_name,
        skill_names=None,
        selection_mode="augment",
        router_enabled=True,
    ):
        selected = list(skill_names or []) or ([skill_name] if skill_name else ["food-safety"])
        return SkillSelection(
            status="forced" if skill_name or skill_names else "selected",
            selected_skill=selected[0],
            selected_skills=selected,
            explicit_skills=selected if skill_name or skill_names else [],
            reason="测试选择。",
            candidate_names=[item.name for item in candidates],
        )

    def load(self, name):
        return SkillDocument(
            name=name,
            description="食品安全问题处理方法。",
            triggers=["鸡肉", "温度"],
            path="food-safety/SKILL.md",
            content="先检索食品安全知识库，再基于证据回答。",
            estimated_tokens=12,
        )


class CapturingPlanner:
    def __init__(self):
        self.question = ""

    def plan(self, request):
        self.question = request.question
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="直接回答",
                steps=[PlanStep(id="s1", kind="no_search", instruction="回答测试问题")],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrieval:
    def collection_name(self, collection=None):
        return collection or "food_safety"


class FakeChat:
    def complete(self, messages):
        return "测试回答"


def test_core_skill_nodes_load_context_before_planner(tmp_path: Path):
    planner = CapturingPlanner()
    service = PermissionAwareAgentService(
        retrieval_service=FakeRetrieval(),
        planner_service=planner,
        planner_tools=[],
        skill_resolver=FakeSkillResolver(),
        chat_client=FakeChat(),
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )

    response = service.ask(
        PermissionAskRequest(
            question="生鸡肉要不要洗？",
            skill_name="food-safety",
            memory_compaction_enabled=False,
            max_retries=0,
        )
    )

    assert response.graph_path[:6] == [
        "load_memory",
        "compact_memory",
        "discover_skills",
        "skill_router",
        "load_skill",
        "planner",
    ]
    assert response.skill_selection is not None
    assert response.skill_selection.selected_skill == "food-safety"
    assert response.loaded_skill is not None
    assert response.loaded_skill.name == "food-safety"
    assert [item.name for item in response.loaded_skills] == ["food-safety"]
    assert "Selected Skill 1" in planner.question
    assert "先检索食品安全知识库" in planner.question
