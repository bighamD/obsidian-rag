from fastapi import APIRouter, Depends, HTTPException, Query, status

from obsidian_rag.config import RagConfig
from obsidian_rag.console_api.dependencies import get_console_config, get_console_memory_store
from obsidian_rag.console_api.schemas import (
    ConsoleConfigResponse,
    ConsoleConversationDeleteResponse,
    ConsoleConversationListResponse,
    ConsoleConversationResponse,
    ConsoleEndpoints,
    ConsoleFeatures,
)


def create_console_router(
    backend_version: str = "v3.12.1",
    *,
    mcp_tools: bool = False,
    collection_routing: bool = False,
    permission_policy: bool = False,
    skills: bool = False,
) -> APIRouter:
    """为共享 console.v1 契约创建带正确学习版本回显的 Router。"""

    router = APIRouter(prefix="/console", tags=["console-v1"])

    @router.get("/config", response_model=ConsoleConfigResponse)
    def console_config(config: RagConfig = Depends(get_console_config)) -> ConsoleConfigResponse:
        return ConsoleConfigResponse(
            contract_version="console.v1",
            backend_version=backend_version,
            features=ConsoleFeatures(
                json_api=True,
                sse=True,
                answer_delta=True,
                reasoning_delta=config.reasoning_stream_enabled,
                conversation_memory=True,
                conversation_management=True,
                collections=True,
                mcp_tools=mcp_tools,
                collection_routing=collection_routing,
                permission_policy=permission_policy,
                skills=skills,
            ),
            endpoints=ConsoleEndpoints(
                ask="/agent/ask",
                stream="/agent/ask/stream",
                conversations="/console/conversations",
                conversation="/console/conversations/{conversation_id}",
                runs="/runs",
                mcp_runtime="/mcp/runtime" if mcp_tools else None,
                collection_runtime="/collections/runtime" if collection_routing else None,
                skills_runtime="/skills/runtime" if skills else None,
            ),
            default_memory_window=3,
        )

    @router.get("/conversations", response_model=ConsoleConversationListResponse)
    def list_conversations(
        limit: int = Query(default=50, ge=1, le=200, description="最多返回多少条最近更新的会话。"),
        memory_store=Depends(get_console_memory_store),
    ) -> ConsoleConversationListResponse:
        return ConsoleConversationListResponse(
            conversations=memory_store.list_conversations(limit=limit),
        )

    @router.get("/conversations/{conversation_id}", response_model=ConsoleConversationResponse)
    def get_conversation(
        conversation_id: str,
        window: int = Query(default=3, ge=0, le=20, description="读取最近多少条原始 Turn。"),
        memory_store=Depends(get_console_memory_store),
    ) -> ConsoleConversationResponse:
        return ConsoleConversationResponse(
            conversation_id=conversation_id,
            memory_snapshot=memory_store.load_snapshot(conversation_id, window=window),
        )

    @router.delete(
        "/conversations/{conversation_id}",
        response_model=ConsoleConversationDeleteResponse,
    )
    def delete_conversation(
        conversation_id: str,
        memory_store=Depends(get_console_memory_store),
    ) -> ConsoleConversationDeleteResponse:
        result = memory_store.delete_conversation(conversation_id)
        if not result.deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在：{conversation_id}",
            )
        return ConsoleConversationDeleteResponse.model_validate(result)

    return router


router = create_console_router()
