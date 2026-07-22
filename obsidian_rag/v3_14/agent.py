from __future__ import annotations

from obsidian_rag.core.schemas import AgentAskResponse, PlanStep
from obsidian_rag.core.sandbox import SandboxRuntime
from obsidian_rag.v3_13.agent import PermissionAwareAgentService


class SandboxAgentService(PermissionAwareAgentService):
    """在 V3.13 完整主链上增加受控 Sandbox Tool 执行和 Artifact 回传。"""

    def __init__(self, *args, sandbox_runtime: SandboxRuntime, **kwargs):
        self.sandbox_runtime = sandbox_runtime
        self._sandbox_run_id: str | None = None
        super().__init__(*args, **kwargs)

    def _initial_state(self, request):
        state = super()._initial_state(request)
        self._sandbox_run_id = state["run_id"]
        return state

    def _catalog_for_request(self, request):
        selected = set(getattr(request, "mcp_tool_names", None) or [])
        catalog = []
        for tool in self.planner_tools:
            if tool.source == "sandbox":
                if getattr(request, "sandbox_enabled", True):
                    catalog.append(tool)
                continue
            if not getattr(request, "mcp_enabled", True):
                continue
            if not selected or tool.name in selected:
                catalog.append(tool)
        return catalog

    def _execute_tool_step(self, step: PlanStep):
        if not (step.tool_name or "").startswith("sandbox::"):
            return super()._execute_tool_step(step)
        run_id = self._sandbox_run_id
        if not run_id:
            return super()._execute_tool_step(step)
        internal_step = step.model_copy(update={"arguments": {**step.arguments, "_run_id": run_id}})
        result = super()._execute_tool_step(internal_step)
        return result.model_copy(update={"arguments": dict(step.arguments)})

    def _response_from_state(self, final_state, request) -> AgentAskResponse:
        response = super()._response_from_state(final_state, request)
        sandbox_used = any(
            (item.tool_name or "").startswith("sandbox::")
            for item in [*final_state.get("step_results", []), *final_state.get("retry_step_results", [])]
        )
        if not sandbox_used:
            return response
        run_id = final_state["run_id"]
        return response.model_copy(
            update={
                "sandbox_workspace_id": run_id,
                "sandbox_artifacts": self.sandbox_runtime.artifacts.list_for_run(run_id),
            }
        )
