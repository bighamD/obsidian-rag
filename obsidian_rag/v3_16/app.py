from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.console_api import create_console_router
from obsidian_rag.v3_10.dependencies import get_run_store
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_16.dependencies import (
    close_postgres_pool,
    get_deep_agent_store,
)
from obsidian_rag.v3_16.routes import agent, approvals, artifacts, health, runtime, sandbox


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        close_postgres_pool()


app = FastAPI(
    title="Obsidian RAG V3.16 DeepAgents Tool Loop & Artifact API",
    version="v3.16",
    description=(
        "官方 DeepAgents create_deep_agent + search_notes ToolMessage + "
        "write_file interrupt_on + Core Sandbox Artifact。"
    ),
    lifespan=lifespan,
)
app.dependency_overrides[get_run_store] = get_deep_agent_store
app.include_router(health.router)
app.include_router(agent.router)
app.include_router(approvals.router)
app.include_router(artifacts.router)
app.include_router(sandbox.router)
app.include_router(runtime.router)
app.include_router(runs.router)
app.include_router(
    create_console_router(
        "v3.16",
        sandbox=True,
        hitl=True,
        deep_agents=True,
        conversation_memory=False,
        conversation_management=False,
    )
)
