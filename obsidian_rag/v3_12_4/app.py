from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_12_2.routes import rerank
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.routes import agent, collections, health, mcp


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager = get_mcp_connection_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(
    title="Obsidian RAG V3.12.4 Unified Knowledge Routing API",
    version="v3.12.4",
    description="Planner、Collection Router、多库 Reranking、MCP Tools、Context、Memory 与 JSON/SSE。",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(collections.router)
app.include_router(mcp.router)
app.include_router(rerank.router)
app.include_router(runs.router)
app.include_router(
    create_console_router(
        "v3.12.4",
        mcp_tools=True,
        collection_routing=True,
    )
)
