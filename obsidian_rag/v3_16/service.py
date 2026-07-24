from __future__ import annotations

from importlib.metadata import version

from obsidian_rag.v3_15.schemas import ApprovalDecisionInput, ApprovalListResponse
from obsidian_rag.v3_16.artifacts import project_artifacts, resolve_artifact
from obsidian_rag.v3_16.schemas import (
    DeepAgentArtifactListResponse,
    DeepAgentRuntimeConfigResponse,
)


class DeepAgentLearningService:
    """V3.16 FastAPI/CLI 门面，聚合 Runtime、Store、Sandbox 与 Artifact。"""

    def __init__(self, *, runtime, store, agent_factory, sandbox, postgres_settings):
        self.runtime = runtime
        self.store = store
        self.agent_factory = agent_factory
        self.sandbox = sandbox
        self.postgres_settings = postgres_settings

    def ask(self, request):
        return self.runtime.ask(request)

    def start_stream(self, request):
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def response(self, run_id: str):
        return self.runtime.get_response(run_id)

    def approval(self, run_id: str):
        return self.store.get_approval(run_id)

    def approvals(self, status: str | None, limit: int) -> ApprovalListResponse:
        return ApprovalListResponse(approvals=self.store.list_approvals(status=status, limit=limit))

    def resume(self, run_id: str, decision: ApprovalDecisionInput):
        return self.runtime.resume(run_id, decision)

    def start_resume_stream(self, run_id: str, decision: ApprovalDecisionInput):
        return self.runtime.start_resume_stream(run_id, decision)

    def artifacts(self, run_id: str) -> DeepAgentArtifactListResponse:
        return DeepAgentArtifactListResponse(run_id=run_id, artifacts=project_artifacts(self.sandbox, run_id))

    def artifact_path(self, artifact_id: str):
        return resolve_artifact(self.sandbox, self.store, artifact_id)

    def runtime_config(self) -> DeepAgentRuntimeConfigResponse:
        return DeepAgentRuntimeConfigResponse(
            version="v3.16",
            framework=f"deepagents {version('deepagents')} on LangGraph",
            model_adapter="langchain-openai ChatOpenAI (Chat Completions)",
            checkpointer_backend="LangGraph PostgresSaver",
            runtime_store_backend="PostgreSQL JSONB + Core Sandbox Workspace",
            tools=["search_notes", "read_file", "write_file", "edit_file", "ls", "glob", "grep"],
            interrupt_tools=["write_file", "edit_file"],
            conversation_memory_enabled=False,
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            resume_endpoint="/approvals/{run_id}/resume",
            resume_stream_endpoint="/approvals/{run_id}/resume/stream",
            artifact_endpoint="/artifacts/{artifact_id}/download",
            sandbox=self.sandbox.runtime_status(),
        )
