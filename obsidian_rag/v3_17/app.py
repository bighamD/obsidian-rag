from contextlib import asynccontextmanager

from fastapi import FastAPI

from obsidian_rag.v3_10.dependencies import get_run_store
from obsidian_rag.v3_10.routes import runs
from obsidian_rag.v3_17.dependencies import close_postgres_pool, get_durable_store
from obsidian_rag.v3_17.routes import agent, approvals, artifacts, console, conversations, memories, recoveries, runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        close_postgres_pool()


app = FastAPI(
    title="Obsidian RAG V3.17 DeepAgents Durable Memory & Context API",
    version="v3.17",
    description=(
        "稳定 Conversation Thread + PostgreSQL Checkpointer + LangGraph Store + "
        "CompositeBackend + DeepAgents Summarization/Offloading。"
    ),
    lifespan=lifespan,
)
app.dependency_overrides[get_run_store] = get_durable_store
app.include_router(runtime.router)
app.include_router(agent.router)
app.include_router(approvals.router)
app.include_router(recoveries.router)
app.include_router(artifacts.router)
app.include_router(conversations.router)
app.include_router(memories.router)
app.include_router(console.router)
app.include_router(runs.router)
