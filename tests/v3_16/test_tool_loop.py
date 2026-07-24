from pathlib import Path
from types import SimpleNamespace

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from obsidian_rag.core.collections.schemas import KnowledgeBaseManifest
from obsidian_rag.core.sandbox.artifacts import ArtifactRegistry
from obsidian_rag.core.sandbox.docker import DockerSandboxBackend
from obsidian_rag.core.sandbox.runtime import SandboxRuntime
from obsidian_rag.core.sandbox.schemas import SandboxProfile
from obsidian_rag.core.sandbox.workspace import SandboxWorkspaceManager
from obsidian_rag.core.tools import ToolRegistry, ToolResult
from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput, ApprovalRecord
from obsidian_rag.v3_16.agent import DeepAgentService
from obsidian_rag.v3_16.backends import DeepAgentsSandboxBackend
from obsidian_rag.v3_16.schemas import DeepAgentAskRequest


class ToolCapableFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, *args, **kwargs):
        return self


def _sandbox(tmp_path: Path) -> SandboxRuntime:
    workspaces = SandboxWorkspaceManager(tmp_path)
    return SandboxRuntime(
        workspaces,
        DockerSandboxBackend(SandboxProfile(), tmp_path),
        ArtifactRegistry(workspaces),
    )


def test_backend_rejects_non_artifact_write(tmp_path):
    backend = DeepAgentsSandboxBackend(_sandbox(tmp_path), "deep_backend")

    result = backend.write("/notes/out.md", "unsafe")

    assert result.error is not None
    assert "/artifacts/" in result.error


def test_search_observation_drives_write_after_resume(tmp_path):
    request = DeepAgentAskRequest(
        question="麻婆豆腐的做法总结成 .md 文档发给我",
        conversation_id="conv_v316_test",
        collection="recipes",
    )
    store = SimpleNamespace(approval=None, request=request)
    store.get_approval = lambda run_id: store.approval
    store.get_request = lambda run_id: store.request
    store.get_response = lambda run_id: None
    store.save_pending_approval = lambda approval_request: (
        setattr(store, "approval", ApprovalRecord(request=approval_request, status="pending")),
        store.approval,
    )[1]
    store.resolve_approval = lambda decision: (
        setattr(
            store,
            "approval",
            ApprovalRecord(
                request=store.approval.request,
                status="resolved",
                decision=decision,
                resolved_at=decision.decided_at,
            ),
        ),
        store.approval,
    )[1]

    model = ToolCapableFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_notes",
                        "args": {"query": "麻婆豆腐", "collection": "recipes"},
                        "id": "call_search",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": "/artifacts/mapo-tofu.md",
                            "content": "# 麻婆豆腐\n\n依据 KB-RECIPE-01。",
                        },
                        "id": "call_write",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Markdown 已生成。"),
        ]
    )
    registry = ToolRegistry()
    registry.register(
        "search_notes",
        lambda **kwargs: ToolResult(
            tool_name="search_notes",
            status="success",
            results=[
                SearchResult(
                    TextChunk(
                        "麻婆豆腐：豆腐焯水，肉末炒香后加入豆瓣酱。",
                        {"chunk_id": "KB-RECIPE-01", "source": "recipes.md"},
                    ),
                    0.9,
                )
            ],
            metadata={"selected_collections": ["recipes"]},
        ),
    )
    service = DeepAgentService(
        model_factory=lambda: model,
        search_registry=registry,
        knowledge_bases=[KnowledgeBaseManifest(id="recipes", collection="recipes", description="菜谱知识库")],
        sandbox_runtime=_sandbox(tmp_path),
        checkpointer=InMemorySaver(),
        store=store,
        default_collection="obsidian_notes",
    )

    waiting = service.begin(request, "deep_test")
    completed = service.resume("deep_test", ApprovalDecisionInput(action="allow"))

    assert waiting.status == "waiting_for_approval"
    assert [call.name for call in waiting.native_response.tool_calls] == ["search_notes", "write_file"]
    assert waiting.native_response.tool_messages[0].tool_name == "search_notes"
    search_observation = waiting.native_response.tool_messages[0].content
    assert search_observation["results"][0]["content"].startswith("麻婆豆腐")
    assert search_observation["results"][0]["collection"] == "recipes"
    assert waiting.native_response.artifacts == []
    assert completed.status == "succeeded"
    assert completed.native_response.final_answer == "Markdown 已生成。"
    assert completed.native_response.artifacts[0].relative_path == "artifacts/mapo-tofu.md"
