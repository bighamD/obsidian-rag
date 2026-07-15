from __future__ import annotations

from collections.abc import Callable
from typing import Any

from obsidian_rag.core.agent.service import AgentService as BaseAgentService
from obsidian_rag.core.mysql_memory import MySQLConversationMemoryStore
from obsidian_rag.core.planner import PlannerService
from obsidian_rag.core.schemas import AgentAskRequest, AgentAskResponse
from obsidian_rag.v3_11.router.service import SkillRouter
from obsidian_rag.v3_11.schemas import (
    SkillAgentResponse,
    SkillAskRequest,
    SkillDocument,
    SkillManifest,
    SkillSelection,
    SkillTraceEvent,
)
from obsidian_rag.v3_11.skills.registry import SkillRegistry, build_skill_context


class SkillAwarePlannerService:
    """在不修改旧 Planner 的前提下，将选中的 Skill Context 注入 Planner。"""

    def __init__(self, planner: PlannerService, skill: SkillDocument | None):
        self.planner = planner
        self.skill = skill

    def plan(self, request):
        if self.skill is None:
            return self.planner.plan(request)
        enriched_request = request.model_copy(
            update={"question": build_skill_context(request.question, self.skill)},
        )
        return self.planner.plan(enriched_request)


class SkillAgentService:
    """V3.11 外层 Skill 流程，后续执行委托给 V3.8.1 Agent。"""

    def __init__(
        self,
        retrieval_service,
        registry: SkillRegistry,
        planner_service: PlannerService | None = None,
        chat_client=None,
        chat_client_factory=None,
        memory_store: MySQLConversationMemoryStore | None = None,
        router: SkillRouter | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.registry = registry
        self.planner_service = planner_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory
        self.memory_store = memory_store
        self.router = router or SkillRouter(
            chat_client=chat_client,
            chat_client_factory=chat_client_factory,
        )

    def ask(self, request: SkillAskRequest) -> SkillAgentResponse:
        return self.ask_with_events(request)

    def ask_with_events(
        self,
        request: SkillAskRequest,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> SkillAgentResponse:
        manifests = self.registry.list_manifests()
        skill_trace: list[SkillTraceEvent] = []
        graph_path = ["discover_skills"]
        _record_skill_event(
            skill_trace,
            event_sink,
            "skill_candidates",
            "discover_skills",
            "candidates",
            f"Registry 发现 {len(manifests)} 个候选 Skill。",
            metadata={"candidate_names": [manifest.name for manifest in manifests]},
        )

        selection = self._select_skill(request, manifests)
        graph_path.append("skill_router")
        _record_skill_event(
            skill_trace,
            event_sink,
            "skill_selected",
            "skill_router",
            "selected" if selection.selected_skill else selection.status,
            selection.reason,
            selected_skill=selection.selected_skill,
            metadata={"status": selection.status, "confidence": selection.confidence},
        )

        loaded_skill: SkillDocument | None = None
        if selection.selected_skill:
            graph_path.append("load_skill")
            try:
                loaded_skill = self.registry.load(selection.selected_skill)
                _record_skill_event(
                    skill_trace,
                    event_sink,
                    "skill_loaded",
                    "load_skill",
                    "loaded",
                    f"已按需加载 {loaded_skill.name} 的 SKILL.md，并准备注入 Planner。",
                    selected_skill=loaded_skill.name,
                    metadata={
                        "path": loaded_skill.path,
                        "estimated_tokens": loaded_skill.estimated_tokens,
                    },
                )
            except (KeyError, OSError, ValueError) as exc:
                selection = selection.model_copy(
                    update={
                        "status": "router_error",
                        "selected_skill": None,
                        "reason": f"Skill 加载失败，已跳过方法注入：{exc}",
                    }
                )
                graph_path.append("skip_skill")
                _record_skill_event(
                    skill_trace,
                    event_sink,
                    "skill_skipped",
                    "skip_skill",
                    "skipped",
                    selection.reason,
                )
        else:
            graph_path.append("skip_skill")
            _record_skill_event(
                skill_trace,
                event_sink,
                "skill_skipped",
                "skip_skill",
                "skipped",
                f"本次不加载 Skill：{selection.reason}",
            )

        planner = self.planner_service or PlannerService(
            chat_client=self.chat_client,
            chat_client_factory=self.chat_client_factory,
        )
        skill_aware_planner = SkillAwarePlannerService(planner, loaded_skill)
        base_agent = BaseAgentService(
            retrieval_service=self.retrieval_service,
            planner_service=skill_aware_planner,
            chat_client=self.chat_client,
            chat_client_factory=self.chat_client_factory,
            memory_store=self.memory_store,
        )
        agent_response = base_agent.ask_with_events(request, event_sink)
        graph_path.extend(agent_response.graph_path)
        return SkillAgentResponse(
            agent_response=agent_response,
            skill_selection=selection,
            loaded_skill=loaded_skill,
            graph_path=graph_path,
            trace=skill_trace,
        )

    def _select_skill(self, request: SkillAskRequest, manifests: list[SkillManifest]) -> SkillSelection:
        names = [manifest.name for manifest in manifests]
        if request.skill_name:
            if request.skill_name not in names:
                return SkillSelection(
                    status="invalid_selection",
                    reason=f"调试参数指定了未知 Skill：{request.skill_name}。",
                    candidate_names=names,
                )
            return SkillSelection(
                status="forced",
                selected_skill=request.skill_name,
                reason="请求通过 skill_name 强制选择 Skill，跳过 LLM Router。",
                candidate_names=names,
            )
        if not request.skill_router_enabled:
            return SkillSelection(
                status="disabled",
                reason="请求关闭了 Skill Router，本次沿用无 Skill 的旧 Agent 流程。",
                candidate_names=names,
            )
        return self.router.route(request.question, manifests)


def _record_skill_event(
    trace: list[SkillTraceEvent],
    event_sink: Callable[[str, dict[str, Any]], None] | None,
    event_name: str,
    node_name: str,
    event_type: str,
    reason: str,
    selected_skill: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = SkillTraceEvent(
        node_name=node_name,
        event_type=event_type,
        selected_skill=selected_skill,
        reason=reason,
        metadata=metadata or {},
    )
    trace.append(event)
    if event_sink is not None:
        event_sink(
            event_name,
            {
                "node_name": node_name,
                "event_type": event_type,
                "selected_skill": selected_skill,
                "reason": reason,
                "metadata": metadata or {},
            },
        )
