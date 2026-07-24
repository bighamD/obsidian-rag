from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.dependencies import get_run_store
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import rerank
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.routes import collections
from obsidian_rag.v3_13.dependencies import get_learning_service as get_v313_learning_service
from obsidian_rag.v3_13.routes import mcp, permissions, skills
from obsidian_rag.v3_14.routes import sandbox
from obsidian_rag.v3_15.dependencies import close_postgres_pool, get_hitl_store, get_learning_service
from obsidian_rag.v3_15.routes import agent, approvals, health, recoveries, runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager = get_mcp_connection_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()
        close_postgres_pool()


app = FastAPI(
    title="Obsidian RAG V3.15 Recovery & HITL API",
    version="v3.15",
    description=(
        "V3.14 Sandbox Agent + LangGraph PostgresSaver、interrupt/resume、"
        "Human-in-the-loop 审批、持久 Run 和 Tool 幂等保护。"
    ),
    lifespan=lifespan,
)
app.dependency_overrides[get_v313_learning_service] = get_learning_service
app.dependency_overrides[get_run_store] = get_hitl_store
app.include_router(health.router)
app.include_router(agent.router)
app.include_router(approvals.router)
app.include_router(recoveries.router)
app.include_router(runtime.router)
app.include_router(sandbox.router)
app.include_router(permissions.router)
app.include_router(skills.router)
app.include_router(collections.router)
app.include_router(mcp.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(
    create_console_router(
        "v3.15",
        mcp_tools=True,
        collection_routing=True,
        permission_policy=True,
        skills=True,
        sandbox=True,
        hitl=True,
    )
)
