from __future__ import annotations

import hashlib
import json
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from obsidian_rag.core.agent.service import (
    AgentState,
    _ACTIVE_EVENT_SINK,
    _copy_state,
    _emit_agent_event,
    _emit_progress_event,
    _now,
    _route_after_evidence_check,
)
from obsidian_rag.core.permissions import PermissionDecision, PermissionReport
from obsidian_rag.core.schemas import AgentAskRequest, AgentTraceStep, Plan, PlanStep, StepResult
from obsidian_rag.v3_14.agent import SandboxAgentService
from obsidian_rag.v3_15.schemas import (
    ApprovalDecision,
    ApprovalDecisionInput,
    ApprovalRecord,
    ApprovalRequest,
    HitlExecutionResult,
    approval_steps_from_plan,
)
from obsidian_rag.v3_15.store import PostgresHitlStore


class HitlAgentState(AgentState, total=False):
    """V3.14 AgentState 加上审批请求、决定和恢复标记。"""

    approval_request: ApprovalRequest
    approval_decision: ApprovalDecision
    resumed_from_checkpoint: bool


class HitlAgentService(SandboxAgentService):
    """在 V3.14 完整主链中插入持久 interrupt/resume 与 Tool 幂等保护。"""

    def __init__(self, *args, checkpointer, hitl_store: PostgresHitlStore, **kwargs):
        # checkpointer：LangGraph PostgresSaver，负责持久化每步 State（支持 interrupt/resume）。
        # hitl_store：业务层持久化，存审批请求、决定和 Tool 幂等结果。
        self.checkpointer = checkpointer
        self.hitl_store = hitl_store
        super().__init__(*args, **kwargs)

    def _build_graph(self):
        """构建带 approval_gate 的 LangGraph，并用持久 checkpointer 编译。"""

        graph = StateGraph(HitlAgentState)
        graph.add_node("load_memory", self._timed_node("load_memory", self._load_memory_node))
        graph.add_node("compact_memory", self._timed_node("compact_memory", self._compact_memory_node))
        if self.skill_resolver is not None:
            graph.add_node("discover_skills", self._timed_node("discover_skills", self._discover_skills_node))
            graph.add_node("skill_router", self._timed_node("skill_router", self._skill_router_node))
            graph.add_node("load_skill", self._timed_node("load_skill", self._load_skill_node))
        graph.add_node("planner", self._timed_node("planner", self._planner_node))
        if self.retrieval_scope_resolver is not None:
            graph.add_node(
                "resolve_retrieval_scope",
                self._timed_node("resolve_retrieval_scope", self._resolve_retrieval_scope_node),
            )
        if self.permission_policy is not None:
            graph.add_node("authorize_steps", self._timed_node("authorize_steps", self._authorize_steps_node))
            graph.add_node("approval_gate", self._timed_node("approval_gate", self._approval_gate_node))
        graph.add_node("execute_steps", self._timed_node("execute_steps", self._execute_steps_node))
        graph.add_node("evidence_check", self._timed_node("evidence_check", self._evidence_check_node))
        graph.add_node("retry_search", self._timed_node("retry_search", self._retry_search_node))
        graph.add_node("build_context", self._timed_node("build_context", self._build_context_node))
        graph.add_node("synthesize_answer", self._timed_node("synthesize_answer", self._synthesize_answer_node))
        graph.add_node("save_memory", self._timed_node("save_memory", self._save_memory_node))

        graph.add_edge(START, "load_memory")
        graph.add_edge("load_memory", "compact_memory")
        if self.skill_resolver is not None:
            graph.add_edge("compact_memory", "discover_skills")
            graph.add_edge("discover_skills", "skill_router")
            graph.add_edge("skill_router", "load_skill")
            graph.add_edge("load_skill", "planner")
        else:
            graph.add_edge("compact_memory", "planner")
        if self.retrieval_scope_resolver is not None:
            graph.add_edge("planner", "resolve_retrieval_scope")
            graph.add_edge(
                "resolve_retrieval_scope",
                "authorize_steps" if self.permission_policy is not None else "execute_steps",
            )
        else:
            graph.add_edge("planner", "authorize_steps" if self.permission_policy is not None else "execute_steps")
        if self.permission_policy is not None:
            # HITL 关键改动：在鉴权后、执行前插入 approval_gate，confirm 步骤在此暂停。
            graph.add_edge("authorize_steps", "approval_gate")
            graph.add_edge("approval_gate", "execute_steps")
        graph.add_edge("execute_steps", "evidence_check")
        graph.add_conditional_edges(
            "evidence_check",
            _route_after_evidence_check,
            {"retry_search": "retry_search", "build_context": "build_context"},
        )
        graph.add_edge("retry_search", "evidence_check")
        graph.add_edge("build_context", "synthesize_answer")
        graph.add_edge("synthesize_answer", "save_memory")
        graph.add_edge("save_memory", END)
        # 传入 checkpointer 才能持久化每步 State，让 interrupt/resume/recover 跨请求生效。
        return graph.compile(checkpointer=self.checkpointer, name="v3_15_recovery_hitl_graph")

    def begin(
        self,
        request: AgentAskRequest,
        run_id: str,
        event_sink=None,
    ) -> HitlExecutionResult:
        """首次执行：用初始 State 从头跑图，遇 confirm 会在 approval_gate 暂停。"""

        state = self._initial_state(request)
        state["run_id"] = run_id
        # 输入完整 state → LangGraph 从 START 开始。
        final_state = self._invoke(state, run_id, event_sink)
        return self._execution_result(final_state, request, run_id)

    def resume(
        self,
        run_id: str,
        decision: ApprovalDecisionInput,
        event_sink=None,
    ) -> HitlExecutionResult:
        """带人工决定恢复：校验 Run 确实停在 interrupt，再用 Command(resume) 继续。"""

        record = self.hitl_store.get_approval(run_id)
        if record is None:
            raise KeyError(f"Approval not found: {run_id}")
        # 防止对同一审批重复提交决定。
        if record.status != "pending":
            raise ValueError(f"Approval already resolved: {run_id}")
        snapshot = self.graph.get_state(self._config(run_id))
        # 只有真正停在 interrupt 的 Run 才能 resume。
        if not snapshot.interrupts:
            raise ValueError(f"Run is not waiting at an interrupt: {run_id}")
        # 输入 Command(resume=...) → interrupt() 处返回该决定，图继续往下。
        final_state = self._invoke(Command(resume=decision.model_dump(mode="json")), run_id, event_sink)
        request = final_state.get("request") or snapshot.values["request"]
        return self._execution_result(final_state, request, run_id)

    def recover(self, run_id: str, event_sink=None) -> HitlExecutionResult:
        """从失败节点前的最近 Checkpoint 继续，不重新创建 AgentState。"""

        snapshot = self.graph.get_state(self._config(run_id))
        if snapshot.interrupts:
            raise ValueError(f"Run is waiting for approval, use resume instead: {run_id}")
        if not snapshot.next:
            raise ValueError(f"Run has no recoverable next node: {run_id}")
        final_state = self._invoke(None, run_id, event_sink)
        request = final_state.get("request") or snapshot.values["request"]
        return self._execution_result(final_state, request, run_id)

    def checkpoint_ready(self, run_id: str = "health_probe") -> bool:
        """探活用：能读取 Checkpoint 说明 PostgresSaver 后端可用。"""

        try:
            self.graph.get_state(self._config(run_id))
        except Exception:
            return False
        return True

    def _invoke(self, input_value, run_id: str, event_sink=None) -> HitlAgentState:
        """统一的图驱动入口：begin/resume/recover 都走这里。

        input_value 决定行为：完整 State=从头跑；Command(resume=...)=从 interrupt 继续；
        None=从最近 Checkpoint 恢复。逐个 State 流出时向 event_sink 推送节点与 trace 事件，
        最终返回最后一个 State（若图立即 interrupt 则回退读快照）。
        """

        # 用 ContextVar 把 event_sink 传给深层节点，避免逐层透传参数。
        token = _ACTIVE_EVENT_SINK.set(event_sink)
        final_state: HitlAgentState | None = None
        trace_cursor = 0
        try:
            for state in self.graph.stream(input_value, config=self._config(run_id), stream_mode="values"):
                final_state = state
                graph_path = state.get("graph_path", [])
                node_name = graph_path[-1] if graph_path else None
                if node_name:
                    timing = next(
                        (item for item in reversed(state.get("node_timings", [])) if item.node_name == node_name),
                        None,
                    )
                    _emit_agent_event(
                        event_sink,
                        "node_finished",
                        {
                            "node_name": node_name,
                            "graph_path": list(graph_path),
                            "started_at": timing.started_at if timing else None,
                            "finished_at": timing.finished_at if timing else None,
                            "duration_ms": timing.duration_ms if timing else None,
                        },
                    )
                    _emit_progress_event(
                        event_sink,
                        node_name=node_name,
                        status="completed",
                        state=state,
                        retrieval_service=self.retrieval_service,
                    )
                # 只推送本轮新增的 trace（trace_cursor 记录上次已推送到哪）。
                traces = state.get("trace", [])
                for trace in traces[trace_cursor:]:
                    _emit_agent_event(event_sink, "trace_event", trace.model_dump(mode="json"))
                trace_cursor = len(traces)
        finally:
            _ACTIVE_EVENT_SINK.reset(token)
        # 图立即 interrupt（如首步就要审批）时 stream 不产出 State，回退读持久快照。
        if final_state is None:
            snapshot = self.graph.get_state(self._config(run_id))
            final_state = dict(snapshot.values)
        return final_state

    def _execution_result(
        self,
        state: HitlAgentState,
        request: AgentAskRequest,
        run_id: str,
    ) -> HitlExecutionResult:
        """把最终 State 包成响应；据快照是否停在 interrupt 判定 succeeded / waiting_for_approval。"""

        snapshot = self.graph.get_state(self._config(run_id))
        approval = self.hitl_store.get_approval(run_id)
        status = "waiting_for_approval" if snapshot.interrupts else "succeeded"
        response = self._response_from_state(state, request)
        if status == "waiting_for_approval":
            response = response.model_copy(update={"answer": "执行已暂停，等待人工审批后继续。"})
        return HitlExecutionResult(status=status, run_id=run_id, response=response, approval=approval)

    def _approval_gate_node(self, state: HitlAgentState) -> HitlAgentState:
        """审批闸口节点：无 confirm 直接放行；有 confirm 则落库 + interrupt 暂停。

        resume 时会带着 Command(resume=...) 二次进入本节点，interrupt() 返回人工决定，
        随后按 allow/edit/deny 改写 Plan 与 PermissionReport，再让图继续执行。
        """

        report = state.get("permission_report")
        confirm_decisions = [item for item in report.decisions if item.decision == "confirm"] if report else []
        # 没有需要确认的副作用步骤：记一条 trace 后直接放行，不暂停。
        if not confirm_decisions:
            state = _copy_state(state)
            state["graph_path"].append("approval_gate")
            state["trace"].append(
                AgentTraceStep(
                    node_name="approval_gate",
                    step_type="approval",
                    result_count=0,
                    reason="没有 confirm 步骤，Graph 无需暂停。",
                )
            )
            return state

        existing = self.hitl_store.get_approval(state["run_id"])
        request = existing.request if existing else ApprovalRequest(
            approval_id=f"approval_{state['run_id']}",
            run_id=state["run_id"],
            conversation_id=state["conversation_id"],
            summary=f"{len(confirm_decisions)} 个 Tool Step 可能产生副作用，需要人工确认。",
            steps=approval_steps_from_plan(state["plan"].steps, confirm_decisions),
            permission_report=report,
            created_at=_now(),
        )
        # 先落库为 pending，再 interrupt。首次运行到此会抛出中断、暂停整张图；
        # resume 时 LangGraph 从 Checkpoint 重放到这里，interrupt() 返回注入的决定 payload。
        self.hitl_store.save_pending_approval(request)
        payload = interrupt(request.model_dump(mode="json"))
        input_decision = ApprovalDecisionInput.model_validate(payload)
        decision = ApprovalDecision(
            approval_id=request.approval_id,
            run_id=state["run_id"],
            action=input_decision.action,
            comment=input_decision.comment,
            step_arguments=input_decision.step_arguments,
            decided_at=_now(),
        )

        state = _copy_state(state)
        state["graph_path"].append("approval_gate")
        state["approval_request"] = request
        state["approval_decision"] = decision
        state["resumed_from_checkpoint"] = True
        state["plan"] = _plan_after_decision(state["plan"], decision)
        state["permission_report"] = self._report_after_decision(state, report, decision)
        self.hitl_store.resolve_approval(decision)
        state["trace"].append(
            AgentTraceStep(
                node_name="approval_gate",
                step_type="approval",
                result_count=len(confirm_decisions),
                reason=f"人工决定为 {decision.action}，Graph 从持久 Checkpoint 恢复。",
                metadata={
                    "approval_id": decision.approval_id,
                    "action": decision.action,
                    "edited_step_ids": sorted(decision.step_arguments),
                },
            )
        )
        return state

    def _report_after_decision(
        self,
        state: HitlAgentState,
        previous: PermissionReport,
        decision: ApprovalDecision,
    ) -> PermissionReport:
        """依据人工决定重算 PermissionReport：edit 重新鉴权，confirm 落定为 allow/deny。"""

        report = previous
        # edit 改了参数，需要用新 Plan 重新过一遍 Policy。
        if decision.action == "edit":
            report = self.permission_policy.authorize(
                plan=state["plan"],
                principal=previous.principal,
                tool_registry=self.tool_registry,
                retrieval_scope=state.get("retrieval_scope"),
                run_id=state["run_id"],
                conversation_id=state["conversation_id"],
            )
        transformed: list[PermissionDecision] = []
        for item in report.decisions:
            if item.decision != "confirm":
                transformed.append(item)
                continue
            if decision.action == "deny":
                transformed.append(item.model_copy(update={"decision": "deny", "reason": "人工审批拒绝该副作用步骤。"}))
            else:
                transformed.append(item.model_copy(update={"decision": "allow", "reason": "人工审批已确认该副作用步骤。"}))
        allow_count = sum(item.decision == "allow" for item in transformed)
        confirm_count = sum(item.decision == "confirm" for item in transformed)
        deny_count = sum(item.decision == "deny" for item in transformed)
        return report.model_copy(
            update={
                "decisions": transformed,
                "allow_count": allow_count,
                "confirm_count": confirm_count,
                "deny_count": deny_count,
                "all_allowed": confirm_count == 0 and deny_count == 0,
                "summary": f"人工审批后：允许 {allow_count} 步，需要确认 {confirm_count} 步，拒绝 {deny_count} 步。",
            }
        )

    def _execute_tool_step(self, step: PlanStep, *, run_id: str | None = None) -> StepResult:
        """带幂等的 Tool 执行：同一 (run_id, step, 参数) 命中缓存则不重复触发副作用。

        recover/resume 可能重放执行节点，幂等键保证已成功的 Tool 结果被复用而非二次执行。
        """

        if not run_id:
            return super()._execute_tool_step(step, run_id=run_id)
        key = _idempotency_key(run_id, step)
        cached = self.hitl_store.get_tool_result(key)
        # 命中缓存：直接返回既有结果，并标注 idempotency_hit。
        if cached is not None:
            return cached.model_copy(
                update={
                    "reason": f"{cached.reason or step.reason}（命中 V3.15 幂等结果，未重复执行 Tool。）",
                    "metadata": {**cached.metadata, "idempotency_key": key, "idempotency_hit": True},
                }
            )
        result = super()._execute_tool_step(step, run_id=run_id)
        # 仅缓存成功结果：失败允许后续重试，成功则持久化以便复用。
        if result.status == "success":
            result = result.model_copy(
                update={"metadata": {**result.metadata, "idempotency_key": key, "idempotency_hit": False}}
            )
            self.hitl_store.save_tool_result(key, run_id, step.id, result, _now())
        return result

    @staticmethod
    def _config(run_id: str) -> dict[str, dict[str, str]]:
        """LangGraph 用 thread_id 定位一条 Run 的 Checkpoint 线程，这里用 run_id。"""

        return {"configurable": {"thread_id": run_id}}


def _plan_after_decision(plan: Plan, decision: ApprovalDecision) -> Plan:
    """当决定为 edit 时，用人工修改后的参数覆盖对应 Step，其余保持不变。"""

    if decision.action != "edit":
        return plan
    steps = [
        step.model_copy(update={"arguments": decision.step_arguments[step.id]})
        if step.id in decision.step_arguments
        else step
        for step in plan.steps
    ]
    return plan.model_copy(update={"steps": steps})


def _idempotency_key(run_id: str, step: PlanStep) -> str:
    """由 run_id + step 标识 + 参数生成稳定哈希键，参数变化即视为不同调用。"""

    payload = json.dumps(
        {
            "run_id": run_id,
            "step_id": step.id,
            "tool_name": step.tool_name,
            "arguments": step.arguments,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
