import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from obsidian_rag.core.permissions import PermissionDecision, PermissionPrincipal, PermissionReport
from obsidian_rag.core.schemas import Plan, PlanStep
from obsidian_rag.v3_15.agent import HitlAgentService, HitlAgentState
from obsidian_rag.v3_15.dependencies import CHECKPOINT_TYPES
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput
from obsidian_rag.v3_15.store import SqliteHitlStore


def test_confirm_interrupts_and_allow_resumes(tmp_path):
    service = object.__new__(HitlAgentService)
    service.hitl_store = SqliteHitlStore(tmp_path / "runtime.sqlite3")
    service.permission_policy = None
    checkpointer = SqliteSaver(
        sqlite3.connect(tmp_path / "checkpoint.sqlite3", check_same_thread=False),
        serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES),
    )
    graph = StateGraph(HitlAgentState)
    graph.add_node("approval_gate", service._approval_gate_node)
    graph.add_edge(START, "approval_gate")
    graph.add_edge("approval_gate", END)
    service.graph = graph.compile(checkpointer=checkpointer)
    step = PlanStep(
        id="s1",
        kind="tool",
        tool_name="sandbox::write_file",
        arguments={"path": "result.txt", "content": "ok"},
        reason="生成文件。",
    )
    report = PermissionReport(
        principal=PermissionPrincipal(),
        decisions=[
            PermissionDecision(
                step_id="s1",
                kind="tool",
                tool_name="sandbox::write_file",
                source="sandbox",
                risk_level="confirm",
                decision="confirm",
                reason="写入文件需要确认。",
            )
        ],
        allow_count=0,
        confirm_count=1,
        deny_count=0,
        all_allowed=False,
        summary="需要确认。",
    )
    config = {"configurable": {"thread_id": "run_test"}}

    paused = service.graph.invoke(
        {
            "run_id": "run_test",
            "conversation_id": "conv_test",
            "plan": Plan(goal="创建文件", steps=[step]),
            "permission_report": report,
            "graph_path": [],
            "trace": [],
            "node_timings": [],
        },
        config,
    )
    resumed = service.graph.invoke(
        Command(resume=ApprovalDecisionInput(action="allow").model_dump()),
        config,
    )

    assert paused["__interrupt__"]
    assert resumed["permission_report"].all_allowed is True
    assert service.hitl_store.get_approval("run_test").status == "resolved"
