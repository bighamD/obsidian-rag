from __future__ import annotations

from obsidian_rag.core.collections import KnowledgeBaseRegistry, RetrievalScopeResolver
from obsidian_rag.core.permissions import InMemoryPermissionAuditStore, PermissionPolicy
from obsidian_rag.core.sandbox import SandboxRuntime
from obsidian_rag.core.schemas import Plan, PlanStep
from obsidian_rag.core.skills import CoreSkillResolver
from obsidian_rag.core.tools import ToolRegistry
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_13.service import PermissionLearningService
from obsidian_rag.v3_14.schemas import (
    SandboxArtifactListResponse,
    SandboxAskRequest,
    SandboxCallRequest,
    SandboxCallResponse,
    SandboxRuntimeConfigResponse,
)


class SandboxLearningService(PermissionLearningService):
    """组合 V3.13 完整主链与 Docker Sandbox Runtime。"""

    def __init__(
        self,
        runtime: StreamingAgentRuntimeService,
        manager: McpConnectionManager,
        registry: KnowledgeBaseRegistry,
        resolver: RetrievalScopeResolver,
        policy: PermissionPolicy,
        audit_store: InMemoryPermissionAuditStore,
        skill_resolver: CoreSkillResolver,
        tool_registry_factory,
        sandbox: SandboxRuntime,
    ):
        super().__init__(
            runtime=runtime,
            manager=manager,
            registry=registry,
            resolver=resolver,
            policy=policy,
            audit_store=audit_store,
            skill_resolver=skill_resolver,
            tool_registry_factory=tool_registry_factory,
        )
        self.sandbox = sandbox

    def ask(self, request: SandboxAskRequest):
        return self.runtime.ask(request)

    def start_stream(self, request: SandboxAskRequest) -> str:
        return self.runtime.start_stream(request)

    def sandbox_call(self, request: SandboxCallRequest) -> SandboxCallResponse:
        registry: ToolRegistry = self.tool_registry_factory()
        step = PlanStep(
            id="sandbox_debug",
            kind="tool",
            tool_name=request.name,
            arguments=request.arguments,
            reason="Swagger 显式 Sandbox 调试。",
        )
        report = self.policy.authorize(
            plan=Plan(goal="显式 Sandbox Tool 调试", steps=[step]),
            principal=request.principal,
            tool_registry=registry,
            retrieval_scope=None,
            run_id=request.run_id,
            conversation_id="sandbox_debug",
        )
        if not report.decisions or report.decisions[0].decision != "allow":
            return SandboxCallResponse(
                permission=report,
                executed=False,
                status="blocked",
                error=report.decisions[0].reason if report.decisions else "没有权限决定。",
            )
        result = registry.run(request.name, **request.arguments, _run_id=request.run_id)
        return SandboxCallResponse(
            permission=report,
            executed=True,
            status=result.status,
            data=result.data,
            error=result.error,
        )

    def artifacts(self, run_id: str) -> SandboxArtifactListResponse:
        return SandboxArtifactListResponse(run_id=run_id, artifacts=self.sandbox.artifacts.list_for_run(run_id))

    def runtime_config(self) -> SandboxRuntimeConfigResponse:
        return SandboxRuntimeConfigResponse(
            version="v3.14",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            sandbox_call_endpoint="/sandbox/call",
            artifacts_endpoint="/sandbox/artifacts/{run_id}",
            sandbox=self.sandbox.runtime_status(),
            permission_policy_enabled=True,
            skill_router_enabled=True,
            approval_resume_enabled=False,
        )
