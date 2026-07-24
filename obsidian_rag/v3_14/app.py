from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import rerank
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.routes import collections
from obsidian_rag.v3_13.dependencies import get_learning_service as get_v313_learning_service
from obsidian_rag.v3_13.routes import mcp, permissions, skills
from obsidian_rag.v3_14.dependencies import get_learning_service
from obsidian_rag.v3_14.routes import agent, health, sandbox


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager = get_mcp_connection_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(
    title="Obsidian RAG V3.14 Sandbox Execution API",
    version="v3.14",
    description=(
        "V3.13 完整 Agent + Planner Collection Selection + Docker Sandbox、"
        "受控文件/命令工具、资源限制和 Artifacts。"
    ),
    lifespan=lifespan,
)
app.dependency_overrides[get_v313_learning_service] = get_learning_service
app.include_router(health.router)
app.include_router(agent.router)
app.include_router(sandbox.router)
app.include_router(permissions.router)
app.include_router(skills.router)
app.include_router(collections.router)
app.include_router(mcp.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(
    create_console_router(
        "v3.14",
        mcp_tools=True,
        collection_routing=True,
        permission_policy=True,
        skills=True,
        sandbox=True,
    )
)
