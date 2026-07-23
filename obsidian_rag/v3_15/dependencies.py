from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from obsidian_rag.core.collections import SearchCollectionPolicy
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_10.dependencies import get_memory_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.dependencies import (
    get_collection_scope_resolver,
    get_config,
    get_knowledge_base_registry,
    get_retrieval_service,
)
from obsidian_rag.v3_13.dependencies import get_permission_audit_store, get_permission_policy, get_skill_resolver
from obsidian_rag.v3_14.dependencies import get_sandbox_runtime
from obsidian_rag.v3_14.registry import build_sandbox_agent_tool_registry
from obsidian_rag.v3_15.agent import HitlAgentService
from obsidian_rag.v3_15.postgres import PostgresStateSettings, create_postgres_pool
from obsidian_rag.v3_15.runtime import HitlRuntimeService
from obsidian_rag.v3_15.service import HitlLearningService
from obsidian_rag.v3_15.store import PostgresHitlStore


CHECKPOINT_TYPES = [
    # V3.15 使用学习仓库内受控模型；显式 allowlist 避免未来 LangGraph 严格模式拒绝反序列化。
    ("obsidian_rag.v3_15.schemas", "HitlAskRequest"),
    ("obsidian_rag.v3_15.schemas", "ApprovalRequest"),
    ("obsidian_rag.v3_15.schemas", "ApprovalDecision"),
    ("obsidian_rag.core.schemas", "Plan"),
    ("obsidian_rag.core.schemas", "PlanRequest"),
    ("obsidian_rag.core.schemas", "PlanStep"),
    ("obsidian_rag.core.schemas", "PlannerTraceStep"),
    ("obsidian_rag.core.schemas", "StepResult"),
    ("obsidian_rag.core.schemas", "ToolObservation"),
    ("obsidian_rag.core.schemas", "MemorySnapshot"),
    ("obsidian_rag.core.schemas", "MemoryTurn"),
    ("obsidian_rag.core.schemas", "MemoryCompactionResult"),
    ("obsidian_rag.core.schemas", "MemoryWriteResult"),
    ("obsidian_rag.core.schemas", "ContextBundle"),
    ("obsidian_rag.core.schemas", "ContextChunk"),
    ("obsidian_rag.core.schemas", "EvidenceCheckResult"),
    ("obsidian_rag.core.schemas", "AgentTraceStep"),
    ("obsidian_rag.core.schemas", "AgentNodeTiming"),
    ("obsidian_rag.core.schemas", "AnswerStreamMetrics"),
    ("obsidian_rag.core.schemas", "PlannerToolDefinition"),
    ("obsidian_rag.core.permissions.schemas", "PermissionPrincipal"),
    ("obsidian_rag.core.permissions.schemas", "PermissionDecision"),
    ("obsidian_rag.core.permissions.schemas", "PermissionReport"),
    ("obsidian_rag.core.collections.schemas", "RetrievalScope"),
    ("obsidian_rag.core.skills.schemas", "SkillManifest"),
    ("obsidian_rag.core.skills.schemas", "SkillSelection"),
    ("obsidian_rag.core.skills.schemas", "SkillDocument"),
]


@lru_cache(maxsize=1)
def get_postgres_settings() -> PostgresStateSettings:
    """从环境变量读取一次 PG 配置并缓存为单例。"""

    return PostgresStateSettings.from_env()


@lru_cache(maxsize=1)
def get_postgres_pool():
    """创建并缓存单例连接池，Checkpoint 与 HITL Store 共用。"""

    return create_postgres_pool(get_postgres_settings())


@lru_cache(maxsize=1)
def get_checkpoint_saver() -> PostgresSaver:
    """构建 LangGraph PostgresSaver（Checkpoint 后端），并建好底层表。"""

    saver = PostgresSaver(
        get_postgres_pool(),
        # allowlist 限定可反序列化的模型，避免 msgpack 反序列化任意类型。
        serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES),
    )
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def get_hitl_store() -> PostgresHitlStore:
    """构建并缓存业务层持久化 store（Run/审批/幂等结果）。"""

    return PostgresHitlStore(get_postgres_pool())


def close_postgres_pool() -> None:
    """FastAPI lifespan 退出时释放连接，未使用数据库时不触发懒加载。"""

    if get_postgres_pool.cache_info().currsize:
        get_postgres_pool().close()
    get_checkpoint_saver.cache_clear()
    get_hitl_store.cache_clear()
    get_postgres_pool.cache_clear()


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    """单例事件总线，桥接后台执行线程与 SSE 响应。"""

    return RunEventBus()


@lru_cache(maxsize=1)
def get_search_collection_policy() -> SearchCollectionPolicy:
    """构建 search_notes 使用的 Collection 选择策略（含默认库与上限）。"""

    return SearchCollectionPolicy(
        registry=get_knowledge_base_registry(),
        default_collection=get_config().collection_name,
        max_collections=3,
    )


def build_agent() -> HitlAgentService:
    """每次现造一个 HitlAgentService：装配检索、Sandbox、Policy、Skill 与持久后端。

    不缓存单例是刻意为之——供 Runtime 在每次/每线程执行时获取干净实例。
    """

    config = get_config()
    retrieval = get_retrieval_service()
    sandbox = get_sandbox_runtime()
    registry, planner_tools, _ = build_sandbox_agent_tool_registry(
        retrieval,
        get_mcp_connection_manager(),
        sandbox,
        get_search_collection_policy(),
        # 副作用 Tool 风险等级设为 confirm → 触发 approval_gate 暂停。
        side_effect_risk_level="confirm",
    )
    return HitlAgentService(
        retrieval_service=retrieval,
        collection_policy=get_search_collection_policy(),
        permission_policy=get_permission_policy(),
        skill_resolver=get_skill_resolver(),
        tool_registry=registry,
        planner_tools=planner_tools,
        sandbox_runtime=sandbox,
        checkpointer=get_checkpoint_saver(),
        hitl_store=get_hitl_store(),
        chat_client_factory=lambda: OpenAIChatClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
            reasoning_stream_enabled=config.reasoning_stream_enabled,
            reasoning_effort=config.reasoning_effort,
        ),
        memory_store=get_memory_store(),
    )


@lru_cache(maxsize=1)
def get_runtime_service() -> HitlRuntimeService:
    """单例 Runtime：注入 Agent 工厂、持久 store 与事件总线。"""

    return HitlRuntimeService(build_agent, get_hitl_store(), get_event_bus())


@lru_cache(maxsize=1)
def get_learning_service() -> HitlLearningService:
    """FastAPI 依赖入口：组装对外的 HitlLearningService 单例。"""

    return HitlLearningService(
        runtime=get_runtime_service(),
        store=get_hitl_store(),
        agent_factory=build_agent,
        registry=get_knowledge_base_registry(),
        resolver=get_collection_scope_resolver(),
        policy=get_permission_policy(),
        audit_store=get_permission_audit_store(),
        skill_resolver=get_skill_resolver(),
        tool_registry_factory=lambda: build_sandbox_agent_tool_registry(
            get_retrieval_service(),
            get_mcp_connection_manager(),
            get_sandbox_runtime(),
            get_search_collection_policy(),
            side_effect_risk_level="confirm",
        )[0],
        sandbox=get_sandbox_runtime(),
        manager=get_mcp_connection_manager(),
        postgres_settings=get_postgres_settings(),
    )
