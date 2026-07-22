from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from obsidian_rag.core.collections import KnowledgeBaseRegistry, RetrievalScope, RetrievalScopeResolver
from obsidian_rag.core.permissions import InMemoryPermissionAuditStore, PermissionPolicy
from obsidian_rag.core.skills import CoreSkillResolver
from obsidian_rag.core.schemas import Plan, PlanStep
from obsidian_rag.core.tools import ToolRegistry
from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_12_3.schemas import McpRefreshResponse, McpRuntimeResponse
from obsidian_rag.v3_13.schemas import (
    PermissionAskRequest,
    PermissionAuditListResponse,
    PermissionEvaluateRequest,
    PermissionEvaluateResponse,
    PermissionMcpCallRequest,
    PermissionMcpCallResponse,
    PermissionRuntimeConfigResponse,
    SkillRouteDebugRequest,
    SkillRouteDebugResponse,
    SkillRuntimeResponse,
)


class PermissionLearningService:
    """组合 V3.12.4 Agent、静态 Policy、审计与独立调试接口。"""

    def __init__(
        self,
        runtime: StreamingAgentRuntimeService,
        manager: McpConnectionManager,
        registry: KnowledgeBaseRegistry,
        resolver: RetrievalScopeResolver,
        policy: PermissionPolicy,
        audit_store: InMemoryPermissionAuditStore,
        skill_resolver: CoreSkillResolver,
        tool_registry_factory: Callable[[], ToolRegistry],
    ):
        self.runtime = runtime
        self.manager = manager
        self.registry = registry
        self.resolver = resolver
        self.policy = policy
        self.audit_store = audit_store
        self.skill_resolver = skill_resolver
        self.tool_registry_factory = tool_registry_factory

    def ask(self, request: PermissionAskRequest) -> ProductionAskResponse:
        return self.runtime.ask(request)

    def start_stream(self, request: PermissionAskRequest) -> str:
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def evaluate(self, request: PermissionEvaluateRequest) -> PermissionEvaluateResponse:
        action = request.action
        step = PlanStep(
            id=action.step_id,
            kind=action.kind,
            query="permission debug" if action.kind == "search" else None,
            tool_name=action.tool_name if action.kind == "tool" else None,
            arguments=action.arguments,
            reason="Swagger 独立 Policy 调试动作。",
        )
        scope = RetrievalScope(
            status="explicit" if action.collections else "not_required",
            selected_collections=action.collections,
            reason="由 /permissions/evaluate 显式提供的调试范围。",
        )
        report = self.policy.authorize(
            plan=Plan(goal="独立权限调试", steps=[step]),
            principal=request.principal,
            tool_registry=self.tool_registry_factory(),
            retrieval_scope=scope,
            run_id=f"policy_{uuid4().hex[:12]}",
            conversation_id="policy_debug",
        )
        return PermissionEvaluateResponse(report=report)

    def audit(self, limit: int) -> PermissionAuditListResponse:
        return PermissionAuditListResponse(
            persistence="in_memory",
            records=self.audit_store.list_records(limit),
        )

    def mcp_runtime(self) -> McpRuntimeResponse:
        return self.manager.runtime()

    def skill_runtime(self) -> SkillRuntimeResponse:
        return SkillRuntimeResponse(
            root=self.skill_resolver.root,
            skills=self.skill_resolver.list_manifests(),
            errors=self.skill_resolver.errors,
        )

    def route_skill(self, request: SkillRouteDebugRequest) -> SkillRouteDebugResponse:
        candidates = self.skill_resolver.list_manifests()
        selection = self.skill_resolver.select(
            question=request.question,
            candidates=candidates,
            skill_name=request.skill_name,
            skill_names=request.skill_names,
            selection_mode=request.skill_selection_mode,
            router_enabled=request.skill_router_enabled,
        )
        return SkillRouteDebugResponse(question=request.question, selection=selection)

    def refresh_mcp(self, server_name: str | None = None, *, reconnect: bool = False) -> McpRefreshResponse:
        runtime = self.manager.refresh(server_name, reconnect=reconnect)
        return McpRefreshResponse(
            refreshed_servers=[server_name] if server_name else [item.name for item in runtime.servers],
            runtime=runtime,
        )

    def call_mcp(self, request: PermissionMcpCallRequest) -> PermissionMcpCallResponse:
        report = self.policy.authorize(
            plan=Plan(
                goal="显式 MCP Tool 调试",
                steps=[
                    PlanStep(
                        id="explicit_mcp_call",
                        kind="tool",
                        tool_name=request.name,
                        arguments=request.arguments,
                        reason="Swagger 显式 MCP 调试调用。",
                    )
                ],
            ),
            principal=request.principal,
            tool_registry=self.tool_registry_factory(),
            retrieval_scope=None,
            run_id=f"policy_{uuid4().hex[:12]}",
            conversation_id="explicit_mcp_call",
        )
        if not report.decisions or report.decisions[0].decision != "allow":
            return PermissionMcpCallResponse(permission=report, executed=False)
        return PermissionMcpCallResponse(
            permission=report,
            executed=True,
            result=self.manager.call_tool(request.name, request.arguments),
        )

    def runtime_config(self) -> PermissionRuntimeConfigResponse:
        return PermissionRuntimeConfigResponse(
            version="v3.13",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            evaluate_endpoint="/permissions/evaluate",
            audit_endpoint="/permissions/audit",
            transports=["stdio", "streamable_http"],
            collection_routing=True,
            multi_collection_retrieval=True,
            permission_policy_enabled=True,
            skill_router_enabled=True,
            decisions=["allow", "confirm", "deny"],
            approval_resume_enabled=False,
            sandbox_enabled=False,
        )
