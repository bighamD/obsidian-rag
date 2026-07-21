from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import rerank
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.routes import collections
from obsidian_rag.v3_13.routes import agent, health, mcp, permissions, skills


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager = get_mcp_connection_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(
    title="Obsidian RAG V3.13 Permission Policy API",
    version="v3.13",
    description="V3.12.4 完整 Agent + Tool allowlist、Schema 校验、scope、allow/confirm/deny 与审计。",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(permissions.router)
app.include_router(skills.router)
app.include_router(collections.router)
app.include_router(mcp.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(
    create_console_router(
        "v3.13",
        mcp_tools=True,
        collection_routing=True,
        permission_policy=True,
        skills=True,
    )
)
