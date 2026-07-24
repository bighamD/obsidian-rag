from pathlib import Path

from obsidian_rag.core.memory import SQLiteConversationMemoryStore
from obsidian_rag.core.schemas import (
    Plan,
    PlanResponse,
    PlanStep,
    PlannerToolDefinition,
)
from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult
from obsidian_rag.v3_12_3.agent import McpAgentService
from obsidian_rag.v3_12_3.schemas import McpAgentAskRequest


class FakePlanner:
    def plan(self, request):
        assert request.tools[0].name == "demo::get_server_time"
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="查询上海时间",
                steps=[
                    PlanStep(
                        id="s1",
                        kind="tool",
                        tool_name="demo::get_server_time",
                        arguments={"timezone": "Asia/Shanghai"},
                    ),
                    PlanStep(id="s2", kind="synthesize", instruction="根据工具结果回答", depends_on=["s1"]),
                ],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrieval:
    def collection_name(self, collection=None):
        return collection or "food_safety"


class FakeChat:
    def complete(self, messages):
        assert "tool_observations" in messages[-1]["content"]
        return "当前上海时间是测试时间。"


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "demo::get_server_time",
        lambda timezone: ToolResult(
            tool_name="demo::get_server_time",
            status="success",
            data={"timezone": timezone, "iso_time": "2026-07-17T10:00:00+08:00"},
            metadata={"source": "mcp", "server_name": "demo", "duration_ms": 3},
        ),
        ToolDefinition(
            name="demo::get_server_time",
            description="返回指定时区时间",
            input_schema={"type": "object", "properties": {"timezone": {"type": "string"}}},
            read_only=True,
            source="mcp",
        ),
    )
    return registry


def test_agent_executes_mcp_tool_and_builds_observation(tmp_path: Path):
    service = McpAgentService(
        retrieval_service=FakeRetrieval(),
        planner_service=FakePlanner(),
        chat_client=FakeChat(),
        tool_registry=_registry(),
        planner_tools=[
            PlannerToolDefinition(
                name="demo::get_server_time",
                description="返回指定时区时间",
                input_schema={"type": "object"},
                read_only=True,
            )
        ],
        memory_store=SQLiteConversationMemoryStore(tmp_path / "memory.sqlite3"),
    )

    response = service.ask(McpAgentAskRequest(question="现在上海时间是多少？", memory_compaction_enabled=False))

    assert response.step_results[0].status == "success"
    assert response.step_results[0].observation is not None
    assert response.context_bundle.tool_observations[0].tool_name == "demo::get_server_time"
    assert response.used_retrieval is False
    assert response.answer == "当前上海时间是测试时间。"
