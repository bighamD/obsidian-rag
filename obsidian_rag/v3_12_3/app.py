from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import rerank
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_3.routes import agent, health, mcp


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager = get_mcp_connection_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(
    title="Obsidian RAG V3.12.3 MCP Agent Integration API",
    version="v3.12.3",
    description="持久 MCP Sessions、Tool-aware Planner、统一 Tool Executor、Reranking、Context 和 JSON/SSE。",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(mcp.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(create_console_router("v3.12.3", mcp_tools=True))
