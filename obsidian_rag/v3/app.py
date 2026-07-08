from __future__ import annotations

from fastapi import FastAPI

from obsidian_rag.v3.routes import agent, health

app = FastAPI(
    title="Obsidian RAG Agent API",
    version="v3",
    description="Lightweight agentic RAG API with search tool traces.",
)

app.include_router(health.router)
app.include_router(agent.router)
